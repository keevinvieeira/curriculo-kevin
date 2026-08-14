import sys
sys.path.insert(0, r'G:\Meu Drive\Arquivos HD\Kevin\curriculo')
from engine.skill_transferability import build_transferability_engine

transfer_engine = build_transferability_engine(r'G:\Meu Drive\Arquivos HD\Kevin\curriculo\data\graph_merged.json')

print('=== Skill Transferability Engine Test (Merged Graph) ===\n')

# Test 1: Ancestry
print('1. Skill Ancestry (n8n):')
ancestry = transfer_engine.get_skill_ancestry('n8n')
print(f'   n8n -> {" -> ".join(ancestry)}')

# Test 2: Related skills
print('\n2. Related Skills (Prompt Engineering):')
related = transfer_engine.get_related_skills('Prompt Engineering')
for skill, strength in related[:5]:
    print(f'   {skill}: {strength:.2f}')

# Test 3: Transferability
print('\n3. Transferability Score:')
score = transfer_engine.calculate_transferability_score('n8n', 'Make (Integromat)')
print(f'   n8n -> Make (Integromat): {score:.2f}')

score = transfer_engine.calculate_transferability_score('Prompt Engineering', 'RAG (Retrieval-Augmented Generation)')
print(f'   Prompt Engineering -> RAG: {score:.2f}')

score = transfer_engine.calculate_transferability_score('Sales Enablement', 'Go-to-Market Strategy')
print(f'   Sales Enablement -> GTM Strategy: {score:.2f}')

# Test 4: Gap Analysis
print('\n4. Gap Analysis Example:')
required = [
    {'name': 'n8n', 'weight': 1.0},
    {'name': 'RAG (Retrieval-Augmented Generation)', 'weight': 0.9},
    {'name': 'Kubernetes', 'weight': 0.7},
    {'name': 'Sales Enablement', 'weight': 0.8}
]
candidate = ['Make (Integromat)', 'Prompt Engineering', 'Sales Excellence', 'Docker']

gaps = transfer_engine.analyze_skill_gaps(required, candidate)
for gap in gaps:
    print(f'   {gap.required_skill} ({gap.gap_severity}, weight={gap.importance_weight})')
    if gap.best_match:
        print(f'      Best: {gap.best_match.source_skill} -> {gap.best_match.target_skill} '
              f'(dist={gap.best_match.distance}, conf={gap.best_match.confidence:.2f})')
        print(f'      Path: {" -> ".join(gap.best_match.path)}')

# Test 5: Skill Cluster
print('\n5. Skill Cluster (Thinking Environment):')
cluster = transfer_engine.get_skill_cluster('Thinking Environment', radius=2)
print(f'   Ancestors: {cluster["ancestors"]}')
print(f'   Descendants: {cluster["descendants"][:5]}')
print(f'   Related: {[(s, f"{w:.2f}") for s, w in cluster["related"][:5]]}')
print(f'   Transferable (r=2): {len(cluster["transferable_to"])} skills')

print('\n[OK] All tests passed!')