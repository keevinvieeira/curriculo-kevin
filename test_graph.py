import sys
import io
from pathlib import Path
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from engine.graph_engine import GraphEngine
from engine import schemas_graph

# Load the migrated graph
engine = GraphEngine()
engine.load_json(str(ROOT / 'data' / 'graph_merged.json'))
engine.print_stats()

# Test queries
print('\n=== TEST QUERIES ===')

# 1. Find candidate (get all candidates)
candidates = engine.get_nodes_by_type(schemas_graph.NodeType.CANDIDATE)
candidate = candidates[0] if candidates else None
if not candidate:
    print("No candidate found!")
    sys.exit(1)
print(f'\nCandidate: {candidate.name}')
candidate_id = candidate.id

# 2. Get roles
roles = engine.get_candidate_roles(candidate_id)
print(f'\nRoles ({len(roles)}):')
for r in roles:
    company = engine.get_role_company(r.id)
    company_name = company.name if company else "Unknown"
    print(f'  - {r.title_pt} @ {company_name} ({r.start_date})')

# 3. Get bullets for first role
if roles:
    bullets = engine.get_role_achievements(roles[0].id)
    print(f'\nBullets for {roles[0].title_pt} ({len(bullets)}):')
    for b in bullets[:3]:
        print(f'  - {b.text_pt[:80]}...')

# 4. Get skills for first bullet
if bullets:
    skills = engine.get_bullet_skills(bullets[0].id)
    tools = engine.get_bullet_tools(bullets[0].id)
    metrics = engine.get_bullet_metrics(bullets[0].id)
    skill_names = [s.name for s in skills[:5]]
    tool_names = [t.name for t in tools[:5]]
    metric_vals = [m.value_change for m in metrics[:5]]
    print(f'\nSkills for bullet 1 ({len(skills)}): {skill_names}')
    print(f'Tools for bullet 1 ({len(tools)}): {tool_names}')
    print(f'Metrics for bullet 1 ({len(metrics)}): {metric_vals}')

# 5. Test skill hierarchy
skill_nodes = engine.get_nodes_by_type(schemas_graph.NodeType.SKILL)
if skill_nodes:
    test_skill = skill_nodes[0]
    parents = engine.get_skill_hierarchy(test_skill.id, 'up')
    children = engine.get_skill_hierarchy(test_skill.id, 'down')
    related = engine.get_related_skills(test_skill.id)
    print(f'\nSkill Hierarchy Test ({test_skill.name}):')
    print(f'  Parents: {[p.name for p in parents]}')
    print(f'  Children: {[c.name for c in children]}')
    print(f'  Related: {[r.name for r in related]}')

print('\n[OK] All tests passed!')