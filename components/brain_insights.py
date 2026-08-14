"""
Career OS — Brain Insights Component
Renders analytics below the Brain Visualizer (expanders, PT-BR).
"""

from __future__ import annotations
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType
from engine import graph_insights as gi


MAX_LIST = 15  # truncation for long gap/orphan lists


def _df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def render_brain_insights(engine: GraphEngine):
    """Render the full insights section below the brain visualizer."""
    st.divider()
    st.subheader("📊 Insights do Grafo")

    # ---------- KPIs ----------
    overview = gi.graph_overview(engine)
    nc = overview["node_counts"]
    cols = st.columns(6)
    cols[0].metric("Nós", overview["total_nodes"])
    cols[1].metric("Conexões", overview["total_edges"])
    cols[2].metric("Skills", nc.get("Skill", 0))
    cols[3].metric("Ferramentas", nc.get("Tool", 0))
    cols[4].metric("Cases", nc.get("Case", 0))
    cols[5].metric("Conquistas", nc.get("BulletPoint", 0))

    # ---------- 1. Roles ----------
    with st.expander("🏆 Cargos mais conectados", expanded=True):
        roles = gi.role_connectivity(engine)
        if roles:
            df = _df(roles)
            df.columns = ["role_id", "Cargo", "Empresa", "Período", "Conquistas", "Cases", "Skills", "Conexões"]
            st.bar_chart(df.set_index("Cargo")[["Conexões", "Skills"]])
            st.dataframe(df.drop(columns=["role_id"]), width="stretch", hide_index=True)
            top = roles[0]
            st.caption(
                f"🥇 **{top['cargo']}** ({top['empresa']}) é seu cargo mais conectado: "
                f"{top['skills']} skills derivadas, {top['conquistas']} conquistas e {top['cases']} cases."
            )
        else:
            st.info("Nenhum cargo encontrado no grafo.")

    # ---------- 2. Tools ----------
    with st.expander("🛠️ Ferramentas mais usadas na carreira"):
        tools = gi.top_tools(engine)
        evidenced = [t for t in tools if t["evidencias"] > 0]
        if evidenced:
            df_top = _df(evidenced[:15])
            df_top.columns = ["Ferramenta", "Tipo", "Proficiência", "Cases", "Bullets", "Evidências"]
            st.bar_chart(df_top.set_index("Ferramenta")["Evidências"])
            df_all = _df(tools)
            df_all.columns = ["Ferramenta", "Tipo", "Proficiência", "Cases", "Bullets", "Evidências"]
            st.dataframe(df_all, width="stretch", hide_index=True)
            top = evidenced[0]
            st.caption(
                f"🥇 **{top['ferramenta']}** lidera com {top['evidencias']} evidências "
                f"({top['cases']} cases + {top['bullets']} conquistas)."
            )
        else:
            st.info("Nenhuma ferramenta com evidência registrada ainda.")

    # ---------- 3. Skills per role ----------
    with st.expander("🎯 Principais skills de cada cargo"):
        roles = gi.role_connectivity(engine)
        if roles:
            options = {f"{r['cargo']} @ {r['empresa']}": r["role_id"] for r in roles}
            selected = st.selectbox("Escolha o cargo:", list(options.keys()), key="insight_role_select")
            skills = gi.skills_by_role(engine, options[selected])
            if skills:
                df = _df(skills)
                df.columns = ["Skill", "Categoria", "Nível", "Anos Exp.", "Via Conquistas", "Via Cases", "Evidências"]
                st.dataframe(df, width="stretch", hide_index=True)
            else:
                st.warning("Este cargo ainda não tem skills conectadas. Mapeie skills nas conquistas/cases dele.")
        else:
            st.info("Nenhum cargo encontrado no grafo.")

    # ---------- 4. Skills & tools per case ----------
    with st.expander("📁 Skills e ferramentas de cada case"):
        case_nodes = sorted(engine.get_nodes_by_type(NodeType.CASE), key=lambda n: n.title)
        if case_nodes:
            options = {n.title: n.id for n in case_nodes}
            selected_title = st.selectbox("Escolha o case:", list(options.keys()), key="insight_case_select")
            profile = gi.case_profile(engine, options[selected_title])
            st.markdown(f"**{profile['titulo']}** — {profile['empresa']}")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**🎯 Skills**")
                if profile["skills"]:
                    st.dataframe(_df(profile["skills"]), width="stretch", hide_index=True)
                else:
                    st.caption("Nenhuma skill mapeada.")
            with col2:
                st.markdown("**🛠️ Ferramentas**")
                if profile["tools"]:
                    st.dataframe(_df(profile["tools"]), width="stretch", hide_index=True)
                else:
                    st.caption("Nenhuma ferramenta mapeada.")
            with col3:
                st.markdown("**📈 Métricas de impacto**")
                if profile["metrics"]:
                    st.dataframe(_df(profile["metrics"]), width="stretch", hide_index=True)
                else:
                    st.caption("Nenhuma métrica vinculada.")
        else:
            st.info("Nenhum case encontrado no grafo.")

    # ---------- 5. Auto discoveries ----------
    with st.expander("💡 Descobertas automáticas"):
        st.markdown("**🏅 Skills mais comprovadas** *(nº de evidências no grafo)*")
        ranking = [r for r in gi.skill_evidence_ranking(engine) if r["evidencias"] > 0]
        if ranking:
            df_rank = _df(ranking[:15])
            df_rank.columns = ["Skill", "Categoria", "Nível", "Evidências"]
            st.bar_chart(df_rank.set_index("Skill")["Evidências"])

        st.markdown("**⚡ Skills subcomprovadas** *(nível 4-5 com até 1 evidência)*")
        under = gi.under_evidenced_skills(engine)
        if under:
            st.warning(
                f"Você declara nível alto em **{len(under)} skills** com pouca ou nenhuma prova no grafo. "
                "Vincule-as a cases/conquistas para dar lastro:"
            )
            df_under = _df(under)
            df_under.columns = ["Skill", "Categoria", "Nível", "Evidências"]
            st.dataframe(df_under, width="stretch", hide_index=True)
        else:
            st.success("Todas as skills de nível alto têm evidências. 🎉")

        st.markdown("**🧬 Perfil de competências** *(skills por categoria)*")
        cats = gi.category_profile(engine)
        if cats:
            df_cat = _df(cats)
            df_cat.columns = ["Categoria", "Skills", "Nível Médio", "Com Evidência"]
            st.bar_chart(df_cat.set_index("Categoria")["Skills"])
            st.dataframe(df_cat, width="stretch", hide_index=True)

        st.markdown("**🏆 Cases mais versáteis** *(skills + tools + métricas)*")
        vcases = gi.versatile_cases(engine)
        if vcases:
            df_v = _df(vcases)
            df_v.columns = ["Case", "Skills", "Tools", "Métricas", "Total"]
            st.dataframe(df_v, width="stretch", hide_index=True)
            st.caption(f"🥇 **{vcases[0]['case']}** é seu case mais completo — ótimo candidato para entrevistas.")

    # ---------- 6. Connectivity & graph health ----------
    with st.expander("🔗 Conexões & Saúde do Grafo"):
        report = gi.connectivity_report(engine)

        cols = st.columns(4)
        cols[0].metric("Componentes", report["n_componentes"])
        cols[1].metric("% conectado", f"{report['pct_conectado']}%")
        cols[2].metric("Ilhas", len(report["ilhas"]))
        cols[3].metric("Nós isolados", len(report["isolados"]))

        if report["n_componentes"] == 1:
            st.success("O grafo está 100% conectado — nenhum nó isolado. 🎉")
        else:
            for island in report["ilhas"]:
                labels = ", ".join(f"{m['label']} ({m['type']})" for m in island["members"][:MAX_LIST])
                extra = f" ... e mais {island['size'] - MAX_LIST}" if island["size"] > MAX_LIST else ""
                st.warning(f"🏝️ **Ilha desconectada** ({island['size']} nós): {labels}{extra}")
            if report["isolados"]:
                labels = ", ".join(f"{i['members'][0]['label']} ({i['members'][0]['type']})" for i in report["isolados"][:MAX_LIST])
                extra = f" ... e mais {len(report['isolados']) - MAX_LIST}" if len(report["isolados"]) > MAX_LIST else ""
                st.warning(f"⚫ **Nós isolados** ({len(report['isolados'])}): {labels}{extra}")

        st.markdown("**🔍 Lacunas de enriquecimento**")
        gap_titles = {
            "bullets_sem_skill": "Conquistas sem skill mapeada",
            "bullets_sem_tool": "Conquistas sem ferramenta mapeada",
            "cargos_sem_case": "Cargos sem case",
            "skills_sem_evidencia": "Skills sem evidência",
            "tools_sem_evidencia": "Ferramentas sem evidência",
            "metricas_sem_origem": "Métricas sem origem",
        }
        has_gaps = False
        for gap_key, title in gap_titles.items():
            items = report["gaps"][gap_key]
            if not items:
                continue
            has_gaps = True
            labels = ", ".join(i["label"] for i in items[:MAX_LIST])
            extra = f" ... e mais {len(items) - MAX_LIST}" if len(items) > MAX_LIST else ""
            st.markdown(f"- **{title}** ({len(items)}): {labels}{extra}")
            st.caption(f"💡 {gi.CONNECTION_SUGGESTIONS[gap_key]}")
        if not has_gaps:
            st.success("Nenhuma lacuna encontrada — grafo bem enriquecido! 🎉")

        st.markdown("**🛠️ Como gerar novas conexões**")
        st.info(
            "As conexões nascem dos **dados de origem**, não do grafo em si. Para enriquecer:\n"
            "1. Atualize `master_resume.json` (skills/tools nas conquistas) e os dados de cases/ontologia em `data/`\n"
            "2. Re-execute os scripts de migração em `scripts/` (migrate_json_to_graph, migrate_cases_to_graph, merge_ontology)\n"
            "3. Recarregue o app — o grafo e estes insights são regenerados automaticamente"
        )
