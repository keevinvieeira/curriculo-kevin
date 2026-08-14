"""
Audit graph_merged.json against master_resume.json.
Flag any claim in cases, star stories, metrics, or bullet embellishments
that cannot be traced to the official master resume text.
"""
from __future__ import annotations
import json
import sys
import io
from pathlib import Path
from typing import Dict, List, Set, Any

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType


def load_master_texts(path: str) -> Set[str]:
    with open(path, "r", encoding="utf-8") as f:
        master = json.load(f)

    chunks: List[str] = []

    # Personal / summary
    summaries = master.get("professional_summaries", [])
    for s in summaries:
        for lang in ("pt", "en"):
            chunks.append(s.get("content", {}).get(lang, ""))

    # Work experience bullets
    for exp in master.get("work_experience", []):
        for b in exp.get("bullets", []):
            for lang in ("pt", "en"):
                chunks.append(b.get(lang, ""))

    # Skills
    for lang, cats in master.get("technical_skills", {}).items():
        for cat in cats:
            chunks.append(cat.get("category", ""))
            chunks.extend(cat.get("skills", []))

    # Education / certs / languages
    for edu in master.get("education", []):
        for lang in ("pt", "en"):
            chunks.append(edu.get("degree", {}).get(lang, ""))
    for cert in master.get("certifications", []):
        chunks.append(cert.get("name", ""))
        for lang in ("pt", "en"):
            chunks.append(cert.get("status", {}).get(lang, ""))
    for lang, items in master.get("languages", {}).items():
        for item in items:
            chunks.append(item.get("language", ""))
            chunks.append(item.get("proficiency", ""))

    # Normalize
    texts = set()
    for c in chunks:
        if not c:
            continue
        texts.add(normalize(c))
    return texts


def normalize(text: str) -> str:
    return " ".join(
        text.lower()
        .replace("%", " %")
        .replace("+", " +")
        .replace("r$", "r$")
        .replace("$", "$")
        .split()
    )


def contained_in_master(claim: str, master_texts: Set[str]) -> bool:
    """Check whether the substance of the claim is directly in the master."""
    if not claim or len(claim.strip()) < 3:
        return True
    norm = normalize(claim)

    # Direct substring match in any normalized master chunk
    for mt in master_texts:
        if norm in mt or mt in norm:
            return True

    # Token overlap heuristic: require all significant tokens present in same chunk
    tokens = [t for t in norm.split() if len(t) > 2 and t not in {"para", "para", "com", "que", "dos", "das", "the", "and", "for", "with", "from", "was", "were"}]
    if not tokens:
        return True

    matches = 0
    for mt in master_texts:
        present = sum(1 for t in tokens if t in mt)
        if present == len(tokens):
            return True
        if present >= max(2, len(tokens) - 1):
            matches += 1

    # Allow if most tokens individually exist across the master (weak fallback)
    if len(tokens) <= 3:
        found_anywhere = sum(1 for t in tokens if any(t in mt for mt in master_texts))
        return found_anywhere == len(tokens)

    return False


def main():
    graph_path = ROOT / "data" / "graph_merged.json"
    master_path = ROOT / "master_resume.json"

    print("=" * 70)
    print("AUDIT: graph_merged.json vs master_resume.json")
    print("=" * 70)

    engine = GraphEngine()
    engine.load_json(str(graph_path))
    master_texts = load_master_texts(str(master_path))

    stats = engine.stats()
    print(f"\nGraph stats: {stats['total_nodes']} nodes / {stats['total_edges']} edges")
    print(f"Master resume chunks indexed: {len(master_texts)}\n")

    unsupported: List[Dict[str, Any]] = []

    # Audit cases
    for case in engine.get_nodes_by_type(NodeType.CASE):
        fields = [
            ("context_pt", case.context_pt),
            ("context_en", case.context_en),
            ("challenge_pt", case.challenge_pt),
            ("challenge_en", case.challenge_en),
            ("problem_pt", case.problem_pt),
            ("problem_en", case.problem_en),
            ("hypotheses_pt", case.hypotheses_pt),
            ("hypotheses_en", case.hypotheses_en),
            ("decisions_pt", case.decisions_pt),
            ("decisions_en", case.decisions_en),
            ("tradeoffs_pt", case.tradeoffs_pt),
            ("tradeoffs_en", case.tradeoffs_en),
            ("results_pt", case.results_pt),
            ("results_en", case.results_en),
        ]
        for field_name, value in fields:
            if not value:
                continue
            if not contained_in_master(value, master_texts):
                unsupported.append({
                    "type": "Case",
                    "node_id": case.id,
                    "title": case.title,
                    "company": case.company,
                    "field": field_name,
                    "value": value[:300],
                })
        for metric in case.metrics:
            if not contained_in_master(metric, master_texts):
                unsupported.append({
                    "type": "Case metric",
                    "node_id": case.id,
                    "title": case.title,
                    "company": case.company,
                    "field": "metric",
                    "value": metric,
                })

    # Audit STAR stories
    for star in engine.get_nodes_by_type(NodeType.STAR_STORY):
        fields = [
            ("situation_pt", star.situation_pt),
            ("situation_en", star.situation_en),
            ("task_pt", star.task_pt),
            ("task_en", star.task_en),
            ("action_pt", star.action_pt),
            ("action_en", star.action_en),
            ("result_pt", star.result_pt),
            ("result_en", star.result_en),
        ]
        for field_name, value in fields:
            if not value:
                continue
            if not contained_in_master(value, master_texts):
                unsupported.append({
                    "type": "STARStory",
                    "node_id": star.id,
                    "title": "",
                    "company": "",
                    "field": field_name,
                    "value": value[:300],
                })

    # Audit bullet points for invented text
    for bullet in engine.get_nodes_by_type(NodeType.BULLET_POINT):
        for lang, value in (("pt", bullet.text_pt), ("en", bullet.text_en)):
            if not value:
                continue
            if not contained_in_master(value, master_texts):
                unsupported.append({
                    "type": "BulletPoint",
                    "node_id": bullet.id,
                    "title": "",
                    "company": "",
                    "field": f"text_{lang}",
                    "value": value[:300],
                })

    # Audit metrics
    for metric in engine.get_nodes_by_type(NodeType.METRIC):
        for field_name in ("indicator", "value_change", "context_pt", "context_en"):
            value = getattr(metric, field_name, "")
            if not value:
                continue
            if not contained_in_master(value, master_texts):
                unsupported.append({
                    "type": "Metric",
                    "node_id": metric.id,
                    "title": "",
                    "company": "",
                    "field": field_name,
                    "value": value[:200],
                })

    print(f"Total unsupported claims found: {len(unsupported)}\n")

    # Group by type for readability
    by_type: Dict[str, List[Dict]] = {}
    for u in unsupported:
        by_type.setdefault(u["type"], []).append(u)

    for t, items in by_type.items():
        print(f"\n--- {t}: {len(items)} item(s) ---")
        for i, item in enumerate(items, 1):
            prefix = f"{item.get('company', '')} - {item.get('title', '')}".strip(" -")
            print(f"\n{i}. [{item['field']}] {prefix}")
            print(f"   {item['value']}")

    # Save report
    report_path = ROOT / "data" / "ontology" / "graph_audit_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "graph_stats": stats,
            "master_chunks": len(master_texts),
            "total_unsupported": len(unsupported),
            "unsupported_by_type": {k: len(v) for k, v in by_type.items()},
            "details": unsupported,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n\nAudit report saved to: {report_path}")


if __name__ == "__main__":
    main()
