"""
Career OS — Merge Ontology into Main Graph
Combines the resume graph with the full skill ontology.
"""

import sys
sys.path.insert(0, r'G:\Meu Drive\Arquivos HD\Kevin\curriculo')

from engine.graph_engine import GraphEngine
from engine import schemas_graph

# Load both graphs
main = GraphEngine()
main.load_json(r'G:\Meu Drive\Arquivos HD\Kevin\curriculo\data\graph_with_cases.json')
print(f"Main graph: {main.stats()['total_nodes']} nodes, {main.stats()['total_edges']} edges")

ontology = GraphEngine()
ontology.load_json(r'G:\Meu Drive\Arquivos HD\Kevin\curriculo\data\graph_ontology.json')
print(f"Ontology graph: {ontology.stats()['total_nodes']} nodes, {ontology.stats()['total_edges']} edges")

# Build name-to-node maps for skills
main_skills = {s.name: s for s in main.get_nodes_by_type(schemas_graph.NodeType.SKILL)}
onto_skills = {s.name: s for s in ontology.get_nodes_by_type(schemas_graph.NodeType.SKILL)}

print(f"\nMain skills: {len(main_skills)}")
print(f"Ontology skills: {len(onto_skills)}")

# Find overlaps
overlap = set(main_skills.keys()) & set(onto_skills.keys())
print(f"\nOverlapping skills: {len(overlap)}")
for name in sorted(overlap):
    print(f"  - {name}")

# Find ontology-only skills
onto_only = set(onto_skills.keys()) - set(main_skills.keys())
print(f"\nOntology-only skills: {len(onto_only)}")

# Strategy: 
# 1. Keep main graph skills (they have DEMONSTRATES/UTILIZED edges to bullets)
# 2. Add ontology-only skills to main graph
# 3. Add SUBSET_OF edges from main skills to ontology categories
# 4. Add RELATED_TO edges from ontology

# Step 1: Add ontology-only skills to main graph
print("\n[1] Adding ontology-only skills to main graph...")
added_skills = 0
onto_skill_nodes = {}  # name -> node_id in main graph

for name in onto_only:
    onto_node = onto_skills[name]
    # Create new skill node in main graph
    new_skill = schemas_graph.SkillNode(
        name=onto_node.name,
        category=onto_node.category,
        level=onto_node.level,
        description_pt=onto_node.description_pt,
        description_en=onto_node.description_en,
        years_experience=onto_node.years_experience
    )
    main.add_node(new_skill)
    onto_skill_nodes[name] = new_skill.id
    added_skills += 1

print(f"  Added {added_skills} new skills")

# Also map existing main skills to their IDs
for name, node in main_skills.items():
    onto_skill_nodes[name] = node.id

# Step 2: Add SUBSET_OF edges from ontology
print("\n[2] Adding SUBSET_OF edges from ontology...")
subset_added = 0
for edge in ontology.get_edges_by_type(schemas_graph.EdgeType.SUBSET_OF):
    source_name = ontology._node_index[edge.source_id].name
    target_name = ontology._node_index[edge.target_id].name
    
    if source_name in onto_skill_nodes and target_name in onto_skill_nodes:
        source_id = onto_skill_nodes[source_name]
        target_id = onto_skill_nodes[target_name]
        
        # Check if edge already exists
        exists = False
        for e in main.get_outgoing_edges(source_id, schemas_graph.EdgeType.SUBSET_OF):
            if e.target_id == target_id:
                exists = True
                break
        
        if not exists:
            main.add_edge(schemas_graph.create_edge(
                schemas_graph.EdgeType.SUBSET_OF, source_id, target_id
            ))
            subset_added += 1

print(f"  Added {subset_added} SUBSET_OF edges")

# Step 3: Add RELATED_TO edges from ontology
print("\n[3] Adding RELATED_TO edges from ontology...")
related_added = 0
for edge in ontology.get_edges_by_type(schemas_graph.EdgeType.RELATED_TO):
    source_name = ontology._node_index[edge.source_id].name
    target_name = ontology._node_index[edge.target_id].name
    
    if source_name in onto_skill_nodes and target_name in onto_skill_nodes:
        source_id = onto_skill_nodes[source_name]
        target_id = onto_skill_nodes[target_name]
        
        # Check if edge already exists
        exists = False
        for e in main.get_outgoing_edges(source_id, schemas_graph.EdgeType.RELATED_TO):
            if e.target_id == target_id:
                exists = True
                break
        
        if not exists:
            main.add_edge(schemas_graph.create_edge(
                schemas_graph.EdgeType.RELATED_TO, source_id, target_id,
                properties={"strength": edge.properties.get("strength", 0.5)}
            ))
            related_added += 1

print(f"  Added {related_added} RELATED_TO edges")

# Step 4: Link main skills to ontology categories (if not already connected)
print("\n[4] Linking main skills to ontology categories...")
# Get category nodes from ontology (they're also SkillNodes with level=5)
category_names = [
    "AI & Machine Learning",
    "Automation & No-Code",
    "Product Discovery",
    "Growth & Marketing",
    "Product Operations",
    "Sales & Operations",
    "Data & Analytics",
    "Technical & Engineering",
    "Leadership & Management",
    "Product Marketing",
    "Strategy & GTM"
]

category_ids = {}
for cat_name in category_names:
    if cat_name in onto_skill_nodes:
        category_ids[cat_name] = onto_skill_nodes[cat_name]
        print(f"  Category node: {cat_name} -> {onto_skill_nodes[cat_name]}")

# The SUBSET_OF edges from step 2 should already connect skills to categories
# Let's verify by checking a few skills
print("\n[5] Verifying connections...")
test_skills = ["n8n", "Prompt Engineering", "Sales Enablement", "Thinking Environment"]
for skill_name in test_skills:
    if skill_name in onto_skill_nodes:
        skill_id = onto_skill_nodes[skill_name]
        parents = main.get_neighbors(skill_id, schemas_graph.EdgeType.SUBSET_OF, "out")
        parent_names = [p.name for p in parents]
        print(f"  {skill_name} -> SUBSET_OF -> {parent_names}")

# Save merged graph
output_path = r"G:\Meu Drive\Arquivos HD\Kevin\curriculo\data\graph_merged.json"
main.save_json(output_path)
print(f"\n[SAVE] Merged graph saved to: {output_path}")
print(f"Final stats: {main.stats()['total_nodes']} nodes, {main.stats()['total_edges']} edges")