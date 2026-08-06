# Career OS — Implementation Plan (Graph-Powered)

## Overview
Transform the current Master Resume Adaptation Studio into a **Graph-Powered Career Intelligence Engine** with Knowledge Graphs, GraphRAG, deterministic Match Scores, and Neural Network Visualization.

---

## Phase 1 — Foundation: Graph Schemas & Engine Core (Sprints 1–2)

### Sprint 1: Schemas & Data Model
| Task | Description | Files |
|------|-------------|-------|
| 1.1 | Create Pydantic graph schemas (`engine/schemas_graph.py`) | `engine/schemas_graph.py` |
| 1.2 | Define Node models: Candidate, Company, Role, Project, BulletPoint, Skill, Tool, Metric, CareerDNA, JobPosting, Requirement | `engine/schemas_graph.py` |
| 1.3 | Define Edge models: WORKED_AS, AT_COMPANY, HAS_ACHIEVEMENT, DEMONSTRATES, UTILIZED, PRODUCED_IMPACT, SUBSET_OF, REQUIRES, MAPS_TO_SKILL | `engine/schemas_graph.py` |
| 1.4 | Add multi-profile support: `user_id`, `profile_id` fields | `engine/schemas_graph.py` |
| 1.5 | Create Competency Ontology base (SUBSET_OF, RELATED_TO hierarchies) | `engine/schemas_graph.py` |

### Sprint 2: Graph Engine & Migration
| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Build `GraphEngine` class with NetworkX backend (`engine/graph_engine.py`) | `engine/graph_engine.py` |
| 2.2 | Implement Cypher-like query interface (subset: MATCH, WHERE, RETURN) | `engine/graph_engine.py` |
| 2.3 | Add Memgraph/Neo4j connector abstraction | `engine/graph_engine.py` |
| 2.4 | Create migration script: `master_resume.json` → Graph nodes/edges | `scripts/migrate_json_to_graph.py` |
| 2.5 | Migrate current companies: Wipro/Meta, Munzner, Meu Barzin, AK | `scripts/migrate_json_to_graph.py` |
| 2.6 | Seed initial Skill Ontology (AI, Growth, Product Ops, Discovery, PMM) | `scripts/seed_ontology.py` |
| 2.7 | Unit tests for graph CRUD + query engine | `tests/test_graph_engine.py` |

**Deliverable:** Working graph with Kevin's full history queryable via Cypher-like API.

---

## Phase 2 — Evidence Library: 30–40 Structured Cases (Sprint 3)

| Task | Description | Files |
|------|-------------|-------|
| 2.1 | Define Case schema (Context, Challenge, Problem, Hypotheses, Decisions, Trade-offs, Results, STAR) | `engine/schemas_graph.py` |
| 2.2 | Create case authoring template/format (JSON + Markdown) | `data/cases/template.md` |
| 2.3 | Author 30–40 cases across all companies (Wipro, Munzner, Meu Barzin, AK, Growth, AI, Consulting) | `data/cases/*.json` |
| 2.4 | Migration script: cases → Graph (Project, BulletPoint, Skill, Tool, Metric nodes) | `scripts/migrate_cases_to_graph.py` |
| 2.5 | Link cases to Roles via HAS_ACHIEVEMENT edges | `scripts/migrate_cases_to_graph.py` |

**Deliverable:** Rich Evidence Library queryable by skill, tool, metric, company.

---

## Phase 3 — Competency Graph & Ontology (Sprint 4)

| Task | Description | Files |
|------|-------------|-------|
| 3.1 | Build full Skill hierarchy (SUBSET_OF): 50+ skills, 4 levels | `data/ontology/skills_taxonomy.json` |
| 3.2 | Add RELATED_TO edges for semantic adjacency | `data/ontology/skills_taxonomy.json` |
| 3.3 | Implement Skill Transferability Engine (shortestPath algorithm) | `engine/skill_transferability.py` |
| 3.4 | Create ontology visualization/validation script | `scripts/validate_ontology.py` |

**Deliverable:** Query `MATCH (s:Skill)-[:SUBSET_OF*]->(parent) RETURN ...` for skill ancestry.

---

## Phase 4 — GraphRAG & Deterministic Match Engine (Sprints 5–6)

### Sprint 5: Triple Extraction & GraphRAG Pipeline
| Task | Description | Files |
|------|-------------|-------|
| 4.1 | Build `JobPostingParser`: URL → clean text + structured requirements | `utils/extraction.py` |
| 4.2 | Implement Triple Extraction via Gemini (Structured Output) | `utils/extraction.py` |
| 4.3 | Create `GraphRAGRetriever`: subgraph context retrieval for job requirements | `engine/graph_rag.py` |
| 4.4 | Replace naive JSON injection with GraphRAG context in resume adaptation | `utils.py` (modify) |
| 4.5 | Add caching layer for extracted job graphs | `engine/graph_rag.py` |

### Sprint 6: Match Score & Gap Analysis
| Task | Description | Files |
|------|-------------|-------|
| 4.6 | Implement Deterministic Match Score (Jaccard Similarity via Cypher) | `engine/match_engine.py` |
| 4.7 | Build Gap Analysis: missing skills/tools with importance weights | `engine/match_engine.py` |
| 4.8 | Create Narrative Engine: AI PM, Growth PM, Product Ops, PMM profiles | `engine/narrative_engine.py` |
| 4.9 | Integration tests: end-to-end job → graph → adapted resume | `tests/test_graph_rag.py` |

**Deliverable:** Job description → Graph → Exact match % + gaps + tailored resume.

---

## Phase 5 — Neural Visualization & Studio UI (Sprints 7–8)

### Sprint 7: Visual Brain Component
| Task | Description | Files |
|------|-------------|-------|
| 5.1 | Build PyVis/NetworkX visualizer component for Streamlit | `components/brain_visualizer.py` |
| 5.2 | Implement "Neural Path Highlighting" on job selection | `components/brain_visualizer.py` |
| 5.3 | Add filters: by company, skill, tool, metric, time | `components/brain_visualizer.py` |
| 5.4 | Export graph as interactive HTML | `components/brain_visualizer.py` |

### Sprint 8: STAR Studio & Generators
| Task | Description | Files |
|------|-------------|-------|
| 5.5 | Create STAR Simulator: browse/filter STAR stories by competency | `components/star_studio.py` |
| 5.6 | Build Interview Q&A Bank (map questions → STAR nodes) | `components/star_studio.py` |
| 5.7 | Enhance generators: ATS Resume, Portfolio HTML, LinkedIn Bio, GTM Cover Letter | `utils/generators.py` |
| 5.8 | Add multi-profile UI (switch between users) | `app.py` (modify) |

**Deliverable:** Full "Career Brain" visual studio in Streamlit.

---

## Phase 6 — Production, Deploy & SaaS Readiness (Sprints 9–10)

| Task | Description | Files |
|------|-------------|-------|
| 6.1 | Real-time sync: Form edits → Graph (MERGE Cypher hooks) | `engine/sync.py` |
| 6.2 | Automated test suite: Graph integrity, Pydantic, Jinja2, Match accuracy | `tests/` |
| 6.3 | Docker Compose: Streamlit + Memgraph + Redis (caching) | `docker-compose.yml` |
| 6.4 | Environment config for multi-user (auth stub, profile isolation) | `config/` |
| 6.5 | Performance benchmarks: GraphRAG latency, token reduction, match accuracy | `benchmarks/` |
| 6.6 | Documentation: Architecture, API, Deployment, Extending Ontology | `docs/` |

**Deliverable:** Production-ready, containerized, multi-user platform.

---

## Dependencies & Order

```
Phase 1 (Sprints 1-2) ──► Phase 2 (Sprint 3) ──► Phase 3 (Sprint 4)
                                                      │
                                                      ▼
Phase 4 (Sprints 5-6) ◄──────────────────────────────┘
      │
      ▼
Phase 5 (Sprints 7-8)
      │
      ▼
Phase 6 (Sprints 9-10)
```

---

## Current State vs Target

| Component | Current | Target (Phase 6) |
|-----------|---------|------------------|
| Data Store | Flat JSON (`master_resume.json`) | Knowledge Graph (NetworkX + Memgraph) |
| Job Analysis | Full JSON → LLM | GraphRAG (subgraph retrieval, –70% tokens) |
| Match Score | LLM guess | Deterministic Jaccard (Cypher) |
| Skills | Flat list | Hierarchical Ontology (SUBSET_OF, RELATED_TO) |
| Cases | Bullet points in JSON | 40 structured Cases with STAR |
| Visualization | None | Interactive Neural Network (PyVis) |
| Generators | Resume + Cover Letter | Resume, Portfolio, LinkedIn, STAR Simulator |
| Architecture | Single-user | Multi-user SaaS-ready |

---

## Quick Start Commands

```bash
# 1. Setup environment
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt

# 2. Run Phase 1 migration (after implementation)
python scripts/migrate_json_to_graph.py

# 3. Run app
streamlit run app.py
```

---

## Next Action
**Confirm Phase 1 scope** → I'll create the folder structure, schemas, graph engine, and migration script.