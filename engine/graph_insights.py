"""
Career OS — Graph Insights
Pure analytics functions over the Knowledge Graph (GraphEngine).
No Streamlit dependency here — returns plain dicts/lists for easy testing.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional

import networkx as nx

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType, EdgeType


# ============================
# HELPERS
# ============================

def node_label(node) -> str:
    """Human-friendly label for any node type."""
    for attr in ("name", "title_pt", "title", "indicator"):
        value = getattr(node, attr, None)
        if value:
            return str(value)
    text = getattr(node, "text_pt", None)
    if text:
        return text[:60] + ("..." if len(text) > 60 else "")
    return str(node.id)[:8]


def _evidence_counts(engine: GraphEngine, target_id: str, edge_type: EdgeType) -> Dict[str, int]:
    """Count incoming edges of a type, grouped by source node type.

    STARStory sources are counted separately because they mirror Cases
    (each Case has exactly one STAR Story with the same skills/tools).
    """
    counts = {"Case": 0, "BulletPoint": 0, "STARStory": 0, "other": 0}
    for edge in engine.get_incoming_edges(target_id, edge_type):
        source = engine.get_node(edge.source_id)
        stype = source.type.value if source else "other"
        counts[stype if stype in counts else "other"] += 1
    return counts


def _role_company_name(engine: GraphEngine, role_id: str) -> str:
    for edge in engine.get_outgoing_edges(role_id, EdgeType.AT_COMPANY):
        company = engine.get_node(edge.target_id)
        if company:
            return company.name
    return ""


def _role_skills(engine: GraphEngine, role_id: str) -> Dict[str, Dict[str, Any]]:
    """Skills reachable from a role via bullets and via cases.

    Returns {skill_id: {"node": skill, "via_bullets": int, "via_cases": int}}
    """
    found: Dict[str, Dict[str, Any]] = {}

    def _track(skill_id: str, origin: str):
        skill = engine.get_node(skill_id)
        if not skill or skill.type != NodeType.SKILL:
            return
        entry = found.setdefault(skill_id, {"node": skill, "via_bullets": 0, "via_cases": 0})
        entry[origin] += 1

    # Role -> BulletPoint -> Skill
    for edge in engine.get_outgoing_edges(role_id, EdgeType.HAS_ACHIEVEMENT):
        bullet_id = edge.target_id
        for dem in engine.get_outgoing_edges(bullet_id, EdgeType.DEMONSTRATES):
            _track(dem.target_id, "via_bullets")

    # Role -> Case -> Skill
    for edge in engine.get_outgoing_edges(role_id, EdgeType.BELONGS_TO_PROJECT):
        case_id = edge.target_id
        for dem in engine.get_outgoing_edges(case_id, EdgeType.DEMONSTRATES):
            _track(dem.target_id, "via_cases")

    return found


# ============================
# OVERVIEW
# ============================

def graph_overview(engine: GraphEngine) -> Dict[str, Any]:
    """High-level KPIs of the graph."""
    node_counts = {nt.value: len(engine.get_nodes_by_type(nt)) for nt in NodeType}
    node_counts = {k: v for k, v in node_counts.items() if v > 0}
    return {
        "total_nodes": len(engine.get_all_nodes()),
        "total_edges": engine.graph.number_of_edges(),
        "node_counts": node_counts,
    }


# ============================
# ROLES
# ============================

def role_connectivity(engine: GraphEngine) -> List[Dict[str, Any]]:
    """Roles ranked by connectivity: bullets, cases, distinct skills, total edges."""
    rows = []
    for role in engine.get_nodes_by_type(NodeType.ROLE):
        bullets = engine.get_outgoing_edges(role.id, EdgeType.HAS_ACHIEVEMENT)
        cases = engine.get_outgoing_edges(role.id, EdgeType.BELONGS_TO_PROJECT)
        skills = _role_skills(engine, role.id)
        rows.append({
            "role_id": role.id,
            "cargo": role.title_pt,
            "empresa": _role_company_name(engine, role.id),
            "periodo": f"{role.start_date} - {role.end_date}",
            "conquistas": len(bullets),
            "cases": len(cases),
            "skills": len(skills),
            "conexoes": engine.graph.degree(role.id),
        })
    rows.sort(key=lambda r: (r["conexoes"], r["skills"]), reverse=True)
    return rows


def skills_by_role(engine: GraphEngine, role_id: str) -> List[Dict[str, Any]]:
    """Skills of a role (via bullets and cases), ranked by evidence then level."""
    skills = _role_skills(engine, role_id)
    rows = []
    for entry in skills.values():
        skill = entry["node"]
        rows.append({
            "skill": skill.name,
            "categoria": skill.category.value,
            "nivel": skill.level,
            "anos_exp": skill.years_experience,
            "via_bullets": entry["via_bullets"],
            "via_cases": entry["via_cases"],
            "evidencias": entry["via_bullets"] + entry["via_cases"],
        })
    rows.sort(key=lambda r: (r["evidencias"], r["nivel"]), reverse=True)
    return rows


# ============================
# TOOLS
# ============================

def top_tools(engine: GraphEngine) -> List[Dict[str, Any]]:
    """Tools ranked by evidence (Cases + Bullets; STAR Stories deduplicated)."""
    rows = []
    for tool in engine.get_nodes_by_type(NodeType.TOOL):
        ev = _evidence_counts(engine, tool.id, EdgeType.UTILIZED)
        total = ev["Case"] + ev["BulletPoint"]
        rows.append({
            "ferramenta": tool.name,
            "tipo": tool.tool_type or "-",
            "proficiencia": tool.proficiency,
            "cases": ev["Case"],
            "bullets": ev["BulletPoint"],
            "evidencias": total,
        })
    rows.sort(key=lambda r: (r["evidencias"], r["proficiencia"]), reverse=True)
    return rows


# ============================
# CASES
# ============================

def case_profile(engine: GraphEngine, case_id: str) -> Dict[str, Any]:
    """Full profile of a case: skills, tools, metrics, linked STAR story."""
    case = engine.get_node(case_id)
    if not case or case.type != NodeType.CASE:
        return {}

    skills, tools, metrics = [], [], []
    for edge in engine.get_outgoing_edges(case_id, EdgeType.DEMONSTRATES):
        skill = engine.get_node(edge.target_id)
        if skill:
            skills.append({"skill": skill.name, "categoria": skill.category.value, "nivel": skill.level})
    for edge in engine.get_outgoing_edges(case_id, EdgeType.UTILIZED):
        tool = engine.get_node(edge.target_id)
        if tool:
            tools.append({"ferramenta": tool.name, "tipo": tool.tool_type or "-", "proficiencia": tool.proficiency})
    for edge in engine.get_outgoing_edges(case_id, EdgeType.PRODUCED_IMPACT):
        metric = engine.get_node(edge.target_id)
        if metric:
            metrics.append({"metrica": metric.indicator, "resultado": metric.value_change})

    skills.sort(key=lambda s: s["nivel"], reverse=True)
    tools.sort(key=lambda t: t["proficiencia"], reverse=True)

    company = ""
    for edge in engine.get_incoming_edges(case_id, EdgeType.HAS_CASE):
        comp = engine.get_node(edge.source_id)
        if comp:
            company = comp.name

    return {
        "case_id": case_id,
        "titulo": case.title,
        "empresa": company or case.company,
        "skills": skills,
        "tools": tools,
        "metrics": metrics,
        "tem_star_story": bool(engine.get_outgoing_edges(case_id, EdgeType.HAS_STAR_STORY)),
    }


def versatile_cases(engine: GraphEngine) -> List[Dict[str, Any]]:
    """Cases ranked by versatility (skills + tools + metrics connected)."""
    rows = []
    for case in engine.get_nodes_by_type(NodeType.CASE):
        n_skills = len(engine.get_outgoing_edges(case.id, EdgeType.DEMONSTRATES))
        n_tools = len(engine.get_outgoing_edges(case.id, EdgeType.UTILIZED))
        n_metrics = len(engine.get_outgoing_edges(case.id, EdgeType.PRODUCED_IMPACT))
        rows.append({
            "case": case.title,
            "skills": n_skills,
            "tools": n_tools,
            "metricas": n_metrics,
            "total": n_skills + n_tools + n_metrics,
        })
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows


# ============================
# SKILL INSIGHTS
# ============================

def skill_evidence_ranking(engine: GraphEngine) -> List[Dict[str, Any]]:
    """Skills ranked by evidence count (Cases + Bullets; STAR deduplicated)."""
    rows = []
    for skill in engine.get_nodes_by_type(NodeType.SKILL):
        ev = _evidence_counts(engine, skill.id, EdgeType.DEMONSTRATES)
        rows.append({
            "skill": skill.name,
            "categoria": skill.category.value,
            "nivel": skill.level,
            "evidencias": ev["Case"] + ev["BulletPoint"],
        })
    rows.sort(key=lambda r: (r["evidencias"], r["nivel"]), reverse=True)
    return rows


def under_evidenced_skills(engine: GraphEngine, min_level: int = 4, max_evidencias: int = 1) -> List[Dict[str, Any]]:
    """High-level skills with little/no evidence — claims without proof."""
    return [
        row for row in skill_evidence_ranking(engine)
        if row["nivel"] >= min_level and row["evidencias"] <= max_evidencias
    ]


def category_profile(engine: GraphEngine) -> List[Dict[str, Any]]:
    """Skill distribution by category with average level and evidence coverage."""
    ranking = skill_evidence_ranking(engine)
    by_cat: Dict[str, Dict[str, Any]] = {}
    for row in ranking:
        cat = by_cat.setdefault(row["categoria"], {"categoria": row["categoria"], "skills": 0,
                                                   "soma_nivel": 0, "com_evidencia": 0})
        cat["skills"] += 1
        cat["soma_nivel"] += row["nivel"]
        if row["evidencias"] > 0:
            cat["com_evidencia"] += 1
    rows = []
    for cat in by_cat.values():
        rows.append({
            "categoria": cat["categoria"],
            "skills": cat["skills"],
            "nivel_medio": round(cat["soma_nivel"] / cat["skills"], 1),
            "com_evidencia": cat["com_evidencia"],
        })
    rows.sort(key=lambda r: r["skills"], reverse=True)
    return rows


# ============================
# GAPS & CONNECTIVITY
# ============================

def data_gaps(engine: GraphEngine) -> Dict[str, List[Dict[str, str]]]:
    """Nodes missing expected connections (enrichment opportunities)."""
    gaps: Dict[str, List[Dict[str, str]]] = {
        "bullets_sem_skill": [],
        "bullets_sem_tool": [],
        "cargos_sem_case": [],
        "skills_sem_evidencia": [],
        "tools_sem_evidencia": [],
        "metricas_sem_origem": [],
    }
    for bullet in engine.get_nodes_by_type(NodeType.BULLET_POINT):
        if not engine.get_outgoing_edges(bullet.id, EdgeType.DEMONSTRATES):
            gaps["bullets_sem_skill"].append({"id": bullet.id, "label": node_label(bullet)})
        if not engine.get_outgoing_edges(bullet.id, EdgeType.UTILIZED):
            gaps["bullets_sem_tool"].append({"id": bullet.id, "label": node_label(bullet)})
    for role in engine.get_nodes_by_type(NodeType.ROLE):
        if not engine.get_outgoing_edges(role.id, EdgeType.BELONGS_TO_PROJECT):
            gaps["cargos_sem_case"].append({"id": role.id, "label": role.title_pt})
    for skill in engine.get_nodes_by_type(NodeType.SKILL):
        if not engine.get_incoming_edges(skill.id, EdgeType.DEMONSTRATES):
            gaps["skills_sem_evidencia"].append({"id": skill.id, "label": skill.name})
    for tool in engine.get_nodes_by_type(NodeType.TOOL):
        if not engine.get_incoming_edges(tool.id, EdgeType.UTILIZED):
            gaps["tools_sem_evidencia"].append({"id": tool.id, "label": tool.name})
    for metric in engine.get_nodes_by_type(NodeType.METRIC):
        if not engine.get_incoming_edges(metric.id, EdgeType.PRODUCED_IMPACT):
            gaps["metricas_sem_origem"].append({"id": metric.id, "label": node_label(metric)})
    return gaps


# Suggestion templates per gap/orphan category (PT-BR, actionable)
CONNECTION_SUGGESTIONS = {
    "bullets_sem_skill": "Mapeie as skills demonstradas em cada conquista (bullet) nos dados de origem e re-execute a migração — isso conecta seus resultados às competências.",
    "bullets_sem_tool": "Indique as ferramentas utilizadas em cada conquista nos dados de origem — isso evidencia seu domínio prático das tools.",
    "cargos_sem_case": "Crie um case para este cargo (contexto, desafio, decisões, resultados) — cases são o conteúdo mais rico do grafo.",
    "skills_sem_evidencia": "Vincule esta skill a um case ou conquista real — skill sem evidência é afirmação sem prova no currículo.",
    "tools_sem_evidencia": "Mostre onde você usou esta ferramenta (case ou conquista) — tool sem evidência perde força no grafo.",
    "metricas_sem_origem": "Conecte esta métrica à conquista/case que a gerou — impacto sem origem não conta história.",
    "no_isolado": "Este nó não tem nenhuma conexão. Vincule-o aos dados de origem (master_resume.json / cases / ontologia) e re-execute os scripts de migração em scripts/.",
}


def connectivity_report(engine: GraphEngine) -> Dict[str, Any]:
    """Disconnected subgraphs and isolated nodes with enrichment suggestions."""
    undirected = engine.graph.to_undirected()
    components = sorted(nx.connected_components(undirected), key=len, reverse=True)

    main_size = len(components[0]) if components else 0
    islands = []
    isolated = []

    for component in components[1:]:
        members = []
        for node_id in component:
            node = engine.get_node(node_id)
            if node:
                members.append({"id": node_id, "label": node_label(node), "type": node.type.value})
        members.sort(key=lambda m: m["type"])
        entry = {"size": len(component), "members": members}
        if len(component) == 1:
            isolated.append(entry)
        else:
            islands.append(entry)

    total = engine.graph.number_of_nodes()
    return {
        "n_componentes": len(components),
        "componente_principal": main_size,
        "pct_conectado": round(100 * main_size / total, 1) if total else 0.0,
        "ilhas": islands,
        "isolados": isolated,
        "gaps": data_gaps(engine),
    }
