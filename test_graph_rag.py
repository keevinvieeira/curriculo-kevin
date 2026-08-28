import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from engine.graph_rag import GraphRAGRetriever, MatchEngine, run_full_analysis
from engine.graph_engine import GraphEngine

# Load graph
engine = GraphEngine()
engine.load_json(str(ROOT / 'data' / 'graph_merged.json'))
print(f"Graph loaded: {engine.stats()['total_nodes']} nodes, {engine.stats()['total_edges']} edges")

# Find a job posting (should be none yet - need to create one via pipeline)
# Let's check what job postings exist
from engine import schemas_graph
jobs = engine.get_nodes_by_type(schemas_graph.NodeType.JOB_POSTING)
print(f"Job postings in graph: {len(jobs)}")

# Since no jobs exist yet, we need to test with the pipeline
# But that requires API key. Let's test the retriever and match engine 
# with a mock job first, or just verify the classes work

print("\n=== Testing GraphRAGRetriever ===")
retriever = GraphRAGRetriever(engine)

# Check candidate
candidates = engine.get_nodes_by_type(schemas_graph.NodeType.CANDIDATE)
if candidates:
    cand = candidates[0]
    print(f"Candidate: {cand.name}")
    
    # Test evidence extraction
    roles = engine.get_candidate_roles(cand.id)
    print(f"Roles: {len(roles)}")
    
    # Get skills from first role
    if roles:
        bullets = engine.get_role_achievements(roles[0].id)
        if bullets:
            skills = engine.get_bullet_skills(bullets[0].id)
            tools = engine.get_bullet_tools(bullets[0].id)
            print(f"First bullet skills: {[s.name for s in skills[:5]]}")
            print(f"First bullet tools: {[t.name for t in tools[:5]]}")

print("\n=== Testing MatchEngine ===")
match_engine = MatchEngine(engine)
print("MatchEngine instantiated successfully")

print("\n[OK] Core classes working - need job posting to test full pipeline")