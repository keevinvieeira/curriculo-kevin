"""
ETAPA 1b (PIPELINE B - SÓ GRAFO) - Inserir a vaga "Senior GTM Engineer"
(Pet Health, LATAM remote, Salesforce + HubSpot + Make/Zapier) no graph_clean.

Slug do artefato: pethealth-gtm-engineer-senior
Empresa: Pet Health (confidencial, slug usado).
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "graph_clean.json"
OUT_PATH = ROOT / "data" / "jobs" / "pethealth-graph-work.json"

JOB = {
    "company": "Pet Health (confidential)",
    "title": "Senior GTM Engineer",
    "url": "confidential",  # vaga postada sem URL publica no momento
}

# Requisitos atomicos extraidos da JD real (Senior GTM Engineer - LATAM remote).
REQUIREMENTS = [
    "Salesforce Sales Cloud expertise",
    "Salesforce Flow (declarative automation)",
    "Apex (procedural Salesforce code)",
    "Salesforce Platform App Builder / Platform Developer I certifications",
    "GTM processes in B2B or PLG SaaS environments",
    "Salesforce + HubSpot integration via middleware/automation tools",
    "Middleware / automation tools (Zapier, Make)",
    "HubSpot Marketing experience",
    "CRM systems, data models, APIs, and SQL",
    "Design and deliver scalable GTM systems and automation workflows",
    "Salesforce declarative tools and automation best practices",
    "English communication (spoken and written)",
    "Startup experience",
    "Experience with Clay / Gong / ChurnZero / Wrike / DocuSign / Zuora / Guru / Slack / Google Workspace",
    "Make.com / Zapier / Xappex G-Connector",
    "Lead enrichment and prioritization (fit, intent, engagement signals)",
    "Sprint execution, roadmap contribution, UAT and documentation",
    "Cross-functional stakeholder management (Finance, Marketing, Sales, CX Ops)",
    "Translate architectural direction into technical requirements and end-to-end GTM implementations",
    "Refactor legacy systems; implement scalable automation for reliability",
]

# Mapa deterministico e EXPLICITO: cada requisito -> tags REAIS que existem no graph_clean.json.
# Toda tag aqui foi conferida contra as 112 skills do grafo. Nenhuma foi inventada.
# Onde a vaga pede coisa que NAO existe no grafo, a lista fica vazia e vira GAP.
REQUIREMENT_TO_TAGS = {
    "Salesforce Sales Cloud expertise": ["crm"],
    "Salesforce Flow (declarative automation)": ["automation", "crm"],
    "Apex (procedural Salesforce code)": [],
    "Salesforce Platform App Builder / Platform Developer I certifications": [],
    "GTM processes in B2B or PLG SaaS environments": ["b2b", "growth", "business-development"],
    "Salesforce + HubSpot integration via middleware/automation tools": ["crm", "automation"],
    "Middleware / automation tools (Zapier, Make)": ["automation"],
    "HubSpot Marketing experience": ["crm"],
    "CRM systems, data models, APIs, and SQL": ["crm", "data", "sql"],
    "Design and deliver scalable GTM systems and automation workflows": ["automation", "crm", "crm-enablement"],
    "Salesforce declarative tools and automation best practices": ["automation", "crm"],
    "English communication (spoken and written)": [],
    "Startup experience": ["zero-to-one"],
    "Experience with Clay / Gong / ChurnZero / Wrike / DocuSign / Zuora / Guru / Slack / Google Workspace": [],
    "Make.com / Zapier / Xappex G-Connector": ["automation"],
    "Lead enrichment and prioritization (fit, intent, engagement signals)": ["lead-generation", "prioritization"],
    "Sprint execution, roadmap contribution, UAT and documentation": ["roadmap", "backlog", "agile", "documentation", "quality-assurance", "project-management"],
    "Cross-functional stakeholder management (Finance, Marketing, Sales, CX Ops)": ["cross-functional", "collaboration", "leadership"],
    "Translate architectural direction into technical requirements and end-to-end GTM implementations": ["product-architecture", "product-strategy", "cross-functional"],
    "Refactor legacy systems; implement scalable automation for reliability": ["automation", "root-cause-analysis", "quality-assurance"],
}


def main() -> None:
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))

    existing_skills = {}
    for n in graph["nodes"]:
        if n["type"] == "Skill":
            tag = n["id"].removeprefix("skill-")
            existing_skills[tag] = n

    mapped = defaultdict(set)
    unmapped = []
    for req in REQUIREMENTS:
        found = {t for t in REQUIREMENT_TO_TAGS.get(req, []) if t in existing_skills}
        if found:
            mapped[req] = found
        else:
            unmapped.append(req)

    job_id = "job-pethealth-gtm-engineer-senior"
    new_nodes = []
    new_edges = []

    new_nodes.append({
        "id": job_id,
        "type": "JobPosting",
        "labels": {"pt": f"{JOB['company']} - {JOB['title']}",
                   "en": f"{JOB['company']} - {JOB['title']}"},
        "url": JOB["url"],
        "size": 2.4,
        "color": "#f59e0b",
        "glow": True,
    })
    new_edges.append({"source": "candidate", "target": job_id, "type": "APPLIED_TO"})

    req_ids = []
    req_to_skills = {}
    for i, req in enumerate(REQUIREMENTS, 1):
        rid = f"req-{i:02d}"
        req_ids.append(rid)
        new_nodes.append({
            "id": rid,
            "type": "Requirement",
            "labels": {"pt": req, "en": req},
            "size": 1.0,
            "color": "#fb923c",
        })
        new_edges.append({"source": job_id, "target": rid, "type": "REQUIRES"})
        tags = mapped.get(req, set())
        req_to_skills[rid] = sorted(tags)
        for tag in tags:
            sid = f"skill-{tag}"
            new_edges.append({"source": rid, "target": sid, "type": "MAPS_TO_SKILL"})

    graph["nodes"].extend(new_nodes)
    graph["edges"].extend(new_edges)
    graph["source"] = "master_resume.json + Pet Health Senior GTM Engineer JD (deterministic map)"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    total_mapped = sum(len(v) for v in req_to_skills.values())
    print(f"Vaga inserida: {JOB['company']} - {JOB['title']}")
    print(f"Requisitos: {len(REQUIREMENTS)}")
    print(f"Requisitos com >=1 skill mapeada: {sum(1 for v in req_to_skills.values() if v)}")
    print(f"Total de ligacoes requisito->skill: {total_mapped}")
    print(f"Requisitos SEM mapeamento (gap real): {len(unmapped)}")
    for u in unmapped:
        print(f"   GAP: {u}")
    print(f"Salvo em: {OUT_PATH.relative_to(ROOT)}")
    print("\nMapa requisito -> skills:")
    for i, req in enumerate(REQUIREMENTS, 1):
        rid = f"req-{i:02d}"
        tags = req_to_skills.get(rid, [])
        print(f"  {i:02d}. {req}")
        print(f"       -> {', '.join(existing_skills[t]['labels']['en'] for t in tags) if tags else '(nenhuma skill do grafo)'}")

    map_path = ROOT / "data" / "jobs" / "pethealth-requirements-map.json"
    map_path.write_text(json.dumps({
        "job_id": job_id,
        "company": JOB["company"],
        "title": JOB["title"],
        "requirements": [
            {"id": f"req-{i:02d}", "text": req, "mapped_skills": sorted(mapped.get(req, set()))}
            for i, req in enumerate(REQUIREMENTS, 1)
        ],
        "unmapped": unmapped,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nMapa isolado salvo em: {map_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
