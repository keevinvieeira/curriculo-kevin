"""
Career OS — Brain Insights Component
Renders analytics below the Brain Visualizer (expanders, PT-BR).

IMPORTANTE: os insights abaixo são derivados EXCLUSIVAMENTE de
`data/graph_clean.json`, que por sua vez é extraído 1:1 de
`master_resume.json` (fonte única de verdade). Nada aqui é inventado:
toda skill/metrica tem evidência no currículo de origem.
"""

from __future__ import annotations
import os
import json
from typing import List, Dict, Any
from collections import Counter

import pandas as pd
import streamlit as st

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType

# Caminho para o grafo limpo (relativo a este arquivo -> ../../data/graph_clean.json)
_HERE = os.path.dirname(os.path.abspath(__file__))
_GRAPH_CLEAN = os.path.normpath(os.path.join(_HERE, "..", "data", "graph_clean.json"))


def _load_clean() -> Dict[str, Any]:
    """Carrega o grafo limpo derivado do master_resume.json."""
    if not os.path.exists(_GRAPH_CLEAN):
        return {"nodes": [], "edges": [], "categories": {}, "stats": {}}
    with open(_GRAPH_CLEAN, "r", encoding="utf-8") as f:
        return json.load(f)


def _df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _by_type(data: Dict[str, Any], t: str) -> List[Dict[str, Any]]:
    return [n for n in data["nodes"] if n.get("type") == t]


def render_brain_insights(engine: GraphEngine):
    """
    Render the full insights section below the brain visualizer.
    Mantém o mesmo modelo visual do Streamlit (KPIs + expanders),
    mas os números vêm do grafo limpo (master_resume.json).
    """
    data = _load_clean()
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    stats = data.get("stats", {})

    companies = _by_type(data, "Company")
    skills = _by_type(data, "Skill")
    metrics = _by_type(data, "Metric")
    roles = _by_type(data, "Role")

    st.divider()
    st.subheader("📊 Insights do Grafo (fonte: master_resume.json)")

    # ---------- KPIs ----------
    cols = st.columns(6)
    cols[0].metric("Nós", stats.get("total_nodes", len(nodes)))
    cols[1].metric("Conexões", stats.get("total_edges", len(edges)))
    cols[2].metric("Skills", stats.get("total_skills", len(skills)))
    cols[3].metric("Empresas", stats.get("total_companies", len(companies)))
    cols[4].metric("Métricas", stats.get("total_metrics", len(metrics)))
    cols[5].metric("Cargos", len(roles))

    # ---------- 1. Skills por empresa ----------
    with st.expander("🏆 Skills por empresa", expanded=True):
        rows = []
        for c in companies:
            name = c["label"]
            c_skills = [s for s in skills if s.get("company") == name]
            c_metrics = [m for m in metrics if m.get("company") == name]
            rows.append({
                "Empresa": name,
                "Skills": len(c_skills),
                "Métricas": len(c_metrics),
                "Detalhe": c.get("details", ""),
            })
        df = _df(rows)
        st.bar_chart(df.set_index("Empresa")["Skills"])
        st.dataframe(df, width="stretch", hide_index=True)
        top = max(rows, key=lambda r: r["Skills"])
        st.caption(
            f"🥇 **{top['Empresa']}** é onde sua stack é mais densa: "
            f"{top['Skills']} skills mapeadas com evidência no currículo."
        )

    # ---------- 2. Métricas reais por empresa ----------
    with st.expander("📊 Métricas reais por empresa"):
        if metrics:
            for c in companies:
                name = c["label"]
                c_metrics = [m for m in metrics if m.get("company") == name]
                if not c_metrics:
                    continue
                st.markdown(f"**{name}** — {len(c_metrics)} métrica(s)")
                for m in c_metrics:
                    ctx = (m.get("context") or m.get("details") or "")
                    ctx = ctx[:140] + ("…" if len(ctx) > 140 else "")
                    st.markdown(f"- `{m['label']}` — {ctx}")
        else:
            st.info("Nenhuma métrica registrada no grafo limpo.")

    # ---------- 3. Skills mais comprovadas ----------
    with st.expander("🎯 Skills mais comprovadas (nº de evidências)"):
        ev = sorted(
            skills,
            key=lambda s: (s.get("evidence_count", 0), s.get("level", 0)),
            reverse=True,
        )
        if ev:
            rows = [{
                "Skill": s["label"],
                "Empresa": s.get("company", "—"),
                "Categoria": s.get("category", "—"),
                "Nível": f"{s.get('level', '?')}/5",
                "Evidências": s.get("evidence_count", 0),
            } for s in ev[:15]]
            df = _df(rows)
            st.bar_chart(df.set_index("Skill")["Evidências"])
            st.dataframe(df, width="stretch", hide_index=True)
            top = ev[0]
            st.caption(
                f"🥇 **{top['label']}** ({top.get('company')}) é sua skill mais comprovada "
                f"no currículo, com {top.get('evidence_count', 0)} evidências."
            )
        else:
            st.info("Nenhuma skill com evidência registrada ainda.")

    # ---------- 4. Perfil de competências por categoria ----------
    with st.expander("🧬 Perfil de competências por categoria"):
        cat = Counter(s.get("category", "—") for s in skills)
        if cat:
            rows = [{"Categoria": k, "Skills": v} for k, v in cat.most_common()]
            df = _df(rows)
            st.bar_chart(df.set_index("Categoria")["Skills"])
            st.dataframe(df, width="stretch", hide_index=True)
            st.caption(
                "Distribuição honesta: reflexo direto do que está no master_resume.json, "
                "sem inflar níveis."
            )

    # ---------- 5. Saúde do grafo (conectividade real) ----------
    with st.expander("🔗 Conexões & Saúde do Grafo"):
        # BFS a partir do candidato
        adj = {}
        for e in edges:
            adj.setdefault(e["source"], set()).add(e["target"])
            adj.setdefault(e["target"], set()).add(e["source"])
        start = next((n["id"] for n in nodes if n["type"] == "Candidate"), None)
        seen = set()
        if start:
            stack = [start]
            while stack:
                cur = stack.pop()
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(adj.get(cur, []))
        total = len(nodes)
        connected = len(seen)
        isolated = total - connected
        pct = round(100 * connected / total, 1) if total else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("Conectados", f"{connected}/{total}")
        c2.metric("% conectado", f"{pct}%")
        c3.metric("Nós isolados", isolated)

        if isolated == 0:
            st.success("O grafo está 100% conectado à origem (você). Nenhum nó órfão. 🎉")
        else:
            st.warning(f"{isolated} nó(s) não conectado(s) à origem.")

        st.markdown("**🛠️ Como regenerar**")
        st.info(
            "Os insights são derivados de `data/graph_clean.json`, extraído 1:1 de "
            "`master_resume.json`. Para atualizar: edite o master, reexecute o extrator "
            "e recarregue o app — sem IA inventando skills no meio do caminho."
        )
