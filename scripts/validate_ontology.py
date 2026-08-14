"""
Career OS — Ontology Validation Script
Validates the skill taxonomy for consistency, completeness, and correctness.
"""

import sys
sys.path.insert(0, r'G:\Meu Drive\Arquivos HD\Kevin\curriculo')

import json
from typing import Dict, Any
from collections import defaultdict
from engine.graph_engine import GraphEngine
from engine import schemas_graph


def validate_ontology(graph_path: str = "data/graph_merged.json") -> Dict[str, Any]:
    """Run comprehensive validation on the skill ontology."""
    
    engine = GraphEngine()
    engine.load_json(graph_path)
    
    skills = engine.get_nodes_by_type(schemas_graph.NodeType.SKILL)
    subset_edges = engine.get_edges_by_type(schemas_graph.EdgeType.SUBSET_OF)
    related_edges = engine.get_edges_by_type(schemas_graph.EdgeType.RELATED_TO)
    
    print(f"=== Ontology Validation Report ===\n")
    print(f"Total Skills: {len(skills)}")
    print(f"SUBSET_OF edges: {len(subset_edges)}")
    print(f"RELATED_TO edges: {len(related_edges)}")
    
    results = {
        "total_skills": len(skills),
        "subset_of_edges": len(subset_edges),
        "related_to_edges": len(related_edges),
        "issues": [],
        "warnings": [],
        "stats": {}
    }
    
    # 1. Check for orphan skills (no SUBSET_OF up, no SUBSET_OF down, no RELATED_TO)
    print("\n[1] Checking for orphan skills...")
    skill_ids = {s.id for s in skills}
    skills_with_subset_up = set()
    skills_with_subset_down = set()
    skills_with_related = set()
    
    for edge in subset_edges:
        skills_with_subset_up.add(edge.source_id)
        skills_with_subset_down.add(edge.target_id)
    
    for edge in related_edges:
        skills_with_related.add(edge.source_id)
        skills_with_related.add(edge.target_id)
    
    connected_skills = skills_with_subset_up | skills_with_subset_down | skills_with_related
    orphan_skills = skill_ids - connected_skills
    
    if orphan_skills:
        print(f"  [WARN] Found {len(orphan_skills)} orphan skills (no connections):")
        for sid in orphan_skills:
            skill = engine.get_node(sid)
            print(f"      - {skill.name}")
            results["warnings"].append(f"Orphan skill: {skill.name}")
    else:
        print("  [OK] No orphan skills")
    
    # 2. Check category coverage (skills should connect to at least one category)
    print("\n[2] Checking category coverage...")
    category_names = [
        "AI & Machine Learning", "Automation & No-Code", "Product Discovery",
        "Growth & Marketing", "Product Operations", "Sales & Operations",
        "Data & Analytics", "Technical & Engineering", "Leadership & Management",
        "Product Marketing", "Strategy & GTM"
    ]
    
    category_ids = {}
    for s in skills:
        if s.name in category_names:
            category_ids[s.name] = s.id
    
    skills_without_category = []
    for skill in skills:
        if skill.name in category_names:
            continue
        # Check if connected to any category via SUBSET_OF
        parents = engine.get_neighbors(skill.id, schemas_graph.EdgeType.SUBSET_OF, "out")
        has_category_parent = any(p.name in category_names for p in parents)
        if not has_category_parent:
            skills_without_category.append(skill.name)
    
    if skills_without_category:
        print(f"  [WARN] {len(skills_without_category)} skills not connected to any category:")
        for name in skills_without_category[:10]:
            print(f"      - {name}")
        if len(skills_without_category) > 10:
            print(f"      ... and {len(skills_without_category) - 10} more")
        results["warnings"].append(f"{len(skills_without_category)} skills without category connection")
    else:
        print("  [OK] All skills connected to categories")
    
    # 3. Check for cycles in SUBSET_OF (should be DAG)
    print("\n[3] Checking for cycles in SUBSET_OF hierarchy...")
    # Build adjacency for cycle detection
    adj = defaultdict(list)
    for edge in subset_edges:
        adj[edge.source_id].append(edge.target_id)
    
    def has_cycle(node, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        rec_stack.remove(node)
        return False
    
    visited = set()
    cycles_found = []
    for skill in skills:
        if skill.id not in visited:
            if has_cycle(skill.id, visited, set()):
                cycles_found.append(skill.name)
    
    if cycles_found:
        print(f"  [ERROR] Cycles detected in: {cycles_found}")
        results["issues"].append(f"Cycles in SUBSET_OF: {cycles_found}")
    else:
        print("  [OK] No cycles in SUBSET_OF hierarchy (DAG)")
    
    # 4. Check RELATED_TO symmetry (should be bidirectional)
    print("\n[4] Checking RELATED_TO symmetry...")
    related_pairs = set()
    for edge in related_edges:
        source_name = engine.get_node(edge.source_id).name
        target_name = engine.get_node(edge.target_id).name
        related_pairs.add((source_name, target_name))
    
    asymmetric = []
    for source, target in related_pairs:
        if (target, source) not in related_pairs:
            asymmetric.append((source, target))
    
    if asymmetric:
        print(f"  [WARN] {len(asymmetric)} asymmetric RELATED_TO edges:")
        for s, t in asymmetric[:10]:
            print(f"      {s} -> {t} (missing reverse)")
        results["warnings"].append(f"{len(asymmetric)} asymmetric RELATED_TO edges")
    else:
        print("  [OK] All RELATED_TO edges are symmetric")
    
    # 5. Skill level distribution
    print("\n[5] Skill level distribution:")
    level_counts = defaultdict(int)
    for skill in skills:
        level_counts[skill.level] += 1
    for level in sorted(level_counts.keys()):
        print(f"  Level {level}: {level_counts[level]} skills")
    results["stats"]["level_distribution"] = dict(level_counts)
    
    # 6. Category distribution
    print("\n[6] Skills per category (including sub-categories):")
    cat_skills = defaultdict(int)
    for skill in skills:
        parents = engine.get_neighbors(skill.id, schemas_graph.EdgeType.SUBSET_OF, "out")
        for p in parents:
            if p.name in category_names:
                cat_skills[p.name] += 1
                break
    for cat in category_names:
        print(f"  {cat}: {cat_skills.get(cat, 0)} skills")
    results["stats"]["category_distribution"] = dict(cat_skills)
    
    # 7. Check for duplicate skill names
    print("\n[7] Checking for duplicate skill names...")
    name_counts = defaultdict(list)
    for skill in skills:
        name_counts[skill.name].append(skill.id)
    
    duplicates = {name: ids for name, ids in name_counts.items() if len(ids) > 1}
    if duplicates:
        print(f"  [ERROR] Duplicate skill names: {duplicates}")
        results["issues"].append(f"Duplicate skills: {duplicates}")
    else:
        print("  [OK] No duplicate skill names")
    
    # 8. Edge weight validation
    print("\n[8] Checking edge weights...")
    invalid_weights = []
    for edge in related_edges:
        weight = edge.properties.get("strength", 0.5)
        if not (0.0 <= weight <= 1.0):
            invalid_weights.append((edge.id, weight))
    
    if invalid_weights:
        print(f"  [WARN] Invalid RELATED_TO weights: {invalid_weights}")
        results["warnings"].append(f"Invalid edge weights: {invalid_weights}")
    else:
        print("  [OK] All edge weights valid (0.0-1.0)")
    
    # Summary
    print(f"\n=== Validation Summary ===")
    print(f"Issues (errors): {len(results['issues'])}")
    print(f"Warnings: {len(results['warnings'])}")
    
    if results["issues"]:
        print("\n[ERROR] ISSUES:")
        for issue in results["issues"]:
            print(f"  - {issue}")
    
    if results["warnings"]:
        print("\n[WARN] WARNINGS:")
        for warning in results["warnings"]:
            print(f"  - {warning}")
    
    if not results["issues"] and not results["warnings"]:
        print("\n[OK] All validations passed!")
    
    return results


def export_validation_report(results: Dict[str, Any], output_path: str = "data/ontology/validation_report.json"):
    """Export validation results to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[EXPORT] Validation report exported to: {output_path}")


if __name__ == "__main__":
    results = validate_ontology()
    export_validation_report(results)