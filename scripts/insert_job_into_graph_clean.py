"""
ETAPA 1b — Inserir a vaga SandboxAQ no grafo LIMPO (graph_clean.json).

Regras:
- Sem LLM. Mapeamento determinístico requisito -> skills existentes no grafo.
- Nenhuma skill inventada: só liga a Requirement a Skill que JÁ existe em graph_clean.json.
- Nao altera o grafo canonico; salva copia de trabalho em data/jobs/sandboxaq-graph-work.json.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PATH = ROOT / "data" / "graph_clean.json"
OUT_PATH = ROOT / "data" / "jobs" / "sandboxaq-graph-work.json"

# --- Vaga real (JD reconstruida de fontes espelho confiaveis do Ashby) ---
JOB = {
    "company": "SandboxAQ",
    "title": "Product & Growth Marketer, AI Simulation",
    "url": "https://www.sandboxaq.com/careers-list?ashby_jid=42615b29-0fcb-429c-b305-8fa6b1137153",
}

# Requisitos atômicos extraidos da JD real (palavras-chave em portugues/ingles para mapear)
REQUIREMENTS = [
    "Product marketing (positioning, messaging by persona)",
    "Growth marketing / demand generation",
    "Go-to-market (GTM)",
    "Inbound marketing",
    "SEO / organic content",
    "Content marketing / thought leadership / case studies / white papers",
    "Email marketing / outbound / nurture / webinars",
    "Sales enablement",
    "CRM e automação de marketing",
    "Funil de vendas / conversão (CRO)",
    "Analytics / marketing metrics / pipeline / performance",
    "Business intelligence (Power BI / dashboards)",
    "AI tools to expand impact (native AI, prompt engineering)",
    "n8n / workflow automation / APIs",
    "Cross-functional collaboration (product, science, commercial)",
    "Stakeholder management",
    "Translate complex technical capability into buyer value",
    "Project management / roadmap / backlog",
    "Facilitação / change communication",
    "Technical / scientific writing",
    "Experiment design / A/B testing",
    "Monetization / subscription models",
]

# Mapa determinístico e EXPLICITO: cada requisito -> tags reais que existem no grafo.
# Sem substring fragil. Toda tag abaixo foi conferida contra graph_clean.json (112 skills).
REQUIREMENT_TO_TAGS = {
    "Product marketing (positioning, messaging by persona)": ["product-positioning", "product-strategy", "marketing", "narratives"],
    "Growth marketing / demand generation": ["growth", "lead-generation", "marketing"],
    "Go-to-market (GTM)": ["product-strategy", "business-development", "marketing"],
    "Inbound marketing": ["inbound", "content-marketing", "seo"],
    "SEO / organic content": ["seo", "content-marketing"],
    "Content marketing / thought leadership / case studies / white papers": ["content-marketing", "content-creation", "copywriting", "narratives", "technical-writing"],
    "Email marketing / outbound / nurture / webinars": ["email-marketing", "paid-media", "content-marketing"],
    "Sales enablement": ["sales-enablement", "crm-enablement", "playbooks", "training", "coaching"],
    "CRM e automação de marketing": ["crm", "automation", "crm-enablement"],
    "Funil de vendas / conversão (CRO)": ["funnel", "cro", "lead-generation"],
    "Analytics / marketing metrics / pipeline / performance": ["analytics", "metrics", "revenue-analytics", "roi"],
    "Business intelligence (Power BI / dashboards)": ["power-bi", "analytics"],
    "AI tools to expand impact (native AI, prompt engineering)": ["ai-implementation", "ai", "prompt-engineering"],
    "n8n / workflow automation / APIs": ["automation"],
    "Cross-functional collaboration (product, science, commercial)": ["cross-functional", "collaboration", "leadership"],
    "Stakeholder management": ["cross-functional", "leadership", "stakeholder" if False else "collaboration"],
    "Translate complex technical capability into buyer value": ["product-positioning", "product-strategy", "narratives", "copywriting"],
    "Project management / roadmap / backlog": ["roadmap", "backlog", "product-strategy"],
    "Facilitação / change communication": ["facilitation", "narratives", "training"],
    "Technical / scientific writing": ["technical-writing", "copywriting", "content-creation"],
    "Experiment design / A/B testing": ["experimentation", "ab-testing" if False else "experimentation"],
    "Monetization / subscription models": ["monetization", "business-model", "business-models"],
}


def norm(text: str) -> str:
    return text.casefold()


def main() -> None:
    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))

    # index de skills existentes: id -> tag (slug extraido do id skill-<tag>)
    existing_skills = {}
    for n in graph["nodes"]:
        if n["type"] == "Skill":
            tag = n["id"].removeprefix("skill-")
            existing_skills[tag] = n

    # mapear requisitos -> tags existentes (somente tags que realmente existem)
    mapped = defaultdict(set)
    unmapped = []
    for req in REQUIREMENTS:
        found = {t for t in REQUIREMENT_TO_TAGS.get(req, []) if t in existing_skills}
        if found:
            mapped[req] = found
        else:
            unmapped.append(req)

    # construir nos da vaga
    job_id = "job-sandboxaq-product-growth-marketer-ai-simulation"
    new_nodes = []
    new_edges = []

    new_nodes.append({
        "id": job_id,
        "type": "JobPosting",
        "labels": {"pt": f"{JOB['company']} — {JOB['title']}",
                    "en": f"{JOB['company']} — {JOB['title']}"},
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
    graph["source"] = "master_resume.json + SandboxAQ JD (deterministic map)"

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

    # relatorio
    total_mapped = sum(len(v) for v in req_to_skills.values())
    print(f"Vaga inserida: {JOB['company']} — {JOB['title']}")
    print(f"Requisitos: {len(REQUIREMENTS)}")
    print(f"Requisitos com >=1 skill mapeada: {sum(1 for v in req_to_skills.values() if v)}")
    print(f"Total de ligacoes requisito->skill: {total_mapped}")
    print(f"Requisitos SEM mapeamento (gap real): {len(unmapped)}")
    for u in unmapped:
        print(f"   GAP: {u}")
    print(f"Salvo em: {OUT_PATH.relative_to(ROOT)}")
    print("\nMapa requisito -> skills:")
    for i, req in enumerate(REQUIREMENTS, 1):
        rid = f"req-{i:01d}" if i < 10 else f"req-{i}"
        tags = req_to_skills.get(rid, [])
        print(f"  {i:02d}. {req}")
        print(f"       -> {', '.join(existing_skills[t]['labels']['en'] for t in tags) if tags else '(nenhuma skill do grafo)'}")

    # salvar tambem o mapa de requisitos isolado para a ETAPA 2
    map_path = ROOT / "data" / "jobs" / "sandboxaq-requirements-map.json"
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
