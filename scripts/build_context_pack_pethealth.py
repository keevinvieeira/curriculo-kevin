"""
ETAPA 2 (PIPELINE B - SO GRAFO) - Pet Health / Senior GTM Engineer.

Recupera do grafo:
  - candidato
  - empresas/cargos (via DEMONSTRATES)
  - skills reais por requisito (via MAPS_TO_SKILL)
  - bullets (Function) que demonstram cada skill
  - metricas das empresas
  - gaps honestos (termos da JD sem skill no grafo)
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK_GRAPH = ROOT / "data" / "jobs" / "pethealth-graph-work.json"
REQ_MAP = ROOT / "data" / "jobs" / "pethealth-requirements-map.json"
OUT = ROOT / "data" / "jobs" / "pethealth-context-pack.json"

# Termos da JD real que, se NAO houver skill correspondente no grafo, sao GAP.
# Fonte: JD Senior GTM Engineer (Pet Health, LATAM). O grafo confirma ausencia.
JD_DOMAIN_TERMS = [
    ("Salesforce Sales Cloud", "ferramenta CRM especifica"),
    ("Salesforce Flow", "ferramenta Salesforce (declarative)"),
    ("Apex", "linguagem Salesforce (procedural)"),
    ("Salesforce Platform App Builder", "certificacao Salesforce"),
    ("Salesforce Platform Developer I", "certificacao Salesforce"),
    ("HubSpot Marketing", "ferramenta CRM/automation especifica"),
    ("Zapier", "middleware/automation"),
    ("Make.com", "middleware/automation"),
    ("Xappex G-Connector", "integracao Salesforce/Google"),
    ("Clay", "ferramenta de enriquecimento de dados"),
    ("Gong", "conversational intelligence / sales"),
    ("ChurnZero", "customer success platform"),
    ("Wrike", "project management tool"),
    ("DocuSign", "e-signature"),
    ("Zuora", "billing / subscription"),
    ("Guru", "knowledge base / enablement"),
    ("Slack", "comunicacao interna"),
    ("Google Workspace", "suite de produtividade"),
    ("TurnZero", "conversational AI / sales"),
    ("Zora (Finance)", "financas internas"),
]


def main() -> None:
    graph = json.loads(WORK_GRAPH.read_text(encoding="utf-8"))
    req_map = json.loads(REQ_MAP.read_text(encoding="utf-8"))

    nodes = {n["id"]: n for n in graph["nodes"]}
    edges_by_type = defaultdict(list)
    for e in graph["edges"]:
        edges_by_type[e["type"]].append((e["source"], e["target"], e))

    def targets(src_id, etype):
        return [t for s, t, _ in edges_by_type[etype] if s == src_id]

    def sources(tgt_id, etype):
        return [s for s, t, _ in edges_by_type[etype] if t == tgt_id]

    cand = nodes["candidate"]
    candidate_block = {
        "name": cand["labels"]["en"],
        "location": cand.get("location", {}),
        "phone": cand.get("phone", ""),
        "email": cand.get("email", ""),
        "linkedin": cand.get("linkedin", ""),
        "github": cand.get("github", ""),
        "website": cand.get("website", ""),
    }

    education = []
    certifications = []
    languages = []
    for n in graph["nodes"]:
        if n["type"] == "Education":
            education.append({"institution": n.get("institution", ""),
                              "degree": n.get("labels", {}),
                              "dates": n.get("dates", "")})
        elif n["type"] == "Certification":
            certifications.append({"name": n.get("labels", {}).get("en", ""),
                                   "issuer": n.get("issuer", ""),
                                   "status": n.get("status", {})})
        elif n["type"] == "Language":
            languages.append({"language": n.get("labels", {}).get("en", ""),
                              "proficiency": n.get("proficiency", "")})

    companies = {}
    for cid in targets("candidate", "WORKED_AT"):
        c = nodes[cid]
        roles = []
        for rid in targets(cid, "HAS_ROLE"):
            r = nodes[rid]
            roles.append({"id": rid, "title": r["labels"], "dates": r.get("dates")})
        companies[cid] = {
            "id": cid,
            "name": c["labels"],
            "location": c.get("location"),
            "dates": c.get("dates"),
            "roles": roles,
        }

    graph_skill_tags = {
        n["id"].removeprefix("skill-"): n["labels"]["en"]
        for n in graph["nodes"] if n["type"] == "Skill"
    }

    per_requirement = []
    recovered_skills = set()
    recovered_functions = {}
    recovered_metrics = {}
    recovered_companies = set()

    for r in req_map["requirements"]:
        rid = r["id"]
        req_text = r["text"]
        skill_ids = targets(rid, "MAPS_TO_SKILL")
        req_skills = []
        for sid in skill_ids:
            sk = nodes[sid]
            tag = sid.removeprefix("skill-")
            recovered_skills.add(tag)
            fids = sources(sid, "DEMONSTRATES_SKILL")
            bullets = []
            for fid in fids:
                fn = nodes.get(fid)
                if fn is None:
                    continue
                recovered_functions[fid] = fn
                bullets.append({
                    "function_id": fid,
                    "company_id": fn.get("company_id"),
                    "role_id": fn.get("role_id"),
                    "pt": fn.get("descriptions", {}).get("pt"),
                    "en": fn.get("descriptions", {}).get("en"),
                    "source": fn.get("source"),
                })
                if fn.get("company_id"):
                    recovered_companies.add(fn["company_id"])
            cids = sources(sid, "DEMONSTRATES")
            for cid in cids:
                recovered_companies.add(cid)
                for mid in targets(cid, "HAS_METRIC"):
                    mt = nodes.get(mid)
                    if mt is None:
                        continue
                    recovered_metrics[mid] = mt
            req_skills.append({
                "skill_id": sid,
                "tag": tag,
                "label_pt": sk["labels"]["pt"],
                "label_en": sk["labels"]["en"],
                "category": sk.get("category"),
                "evidence_count": sk.get("evidence_count", 0),
                "bullets": bullets,
            })
        per_requirement.append({
            "requirement_id": rid,
            "requirement_text": req_text,
            "skills": req_skills,
            "n_bullets": sum(len(s["bullets"]) for s in req_skills),
        })

    gaps = []
    for term, kind in JD_DOMAIN_TERMS:
        found = any(term.split("/")[0].strip().lower() in (en.lower() + " " + tag.lower())
                    for tag, en in graph_skill_tags.items())
        if not found:
            gaps.append({"term": term, "kind": kind})

    pack = {
        "job_id": req_map["job_id"],
        "company": req_map["company"],
        "title": req_map["title"],
        "source": "GRAPH ONLY (data/jobs/pethealth-graph-work.json). No master_resume, no LLM.",
        "candidate": candidate_block,
        "education": education,
        "certifications": certifications,
        "languages": languages,
        "companies": [companies[c] for c in recovered_companies if c in companies],
        "recovered_skills": sorted(recovered_skills),
        "recovered_skills_count": len(recovered_skills),
        "recovered_bullets_count": len(recovered_functions),
        "recovered_metrics_count": len(recovered_metrics),
        "per_requirement": per_requirement,
        "metrics": [
            {
                "company": nodes.get(m["company_id"], {}).get("labels", {}).get("en"),
                "value": m["labels"]["en"],
                "name_en": m.get("names", {}).get("en"),
                "context_en": m.get("contexts", {}).get("en"),
            }
            for m in recovered_metrics.values()
        ],
        "gaps": gaps,
        "coverage": {
            "requirements_total": len(req_map["requirements"]),
            "requirements_with_evidence": sum(1 for p in per_requirement if p["n_bullets"] > 0),
        },
    }

    OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== CONTEXT PACK (so o grafo) - Pet Health / Senior GTM Engineer ===")
    print(f"Empresas recuperadas: {len(pack['companies'])}")
    print(f"Skills recuperadas: {pack['recovered_skills_count']}")
    print(f"Bullets (Functions) recuperados: {pack['recovered_bullets_count']}")
    print(f"Metricas recuperadas: {pack['recovered_metrics_count']}")
    print(f"Cobertura: {pack['coverage']['requirements_with_evidence']}/{pack['coverage']['requirements_total']} requisitos com >=1 bullet")
    print(f"\nGAPS (termos da JD sem skill no grafo): {len(gaps)}")
    for g in gaps:
        print(f"   - {g['term']}  [{g['kind']}]")
    print(f"\nSalvo em: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
