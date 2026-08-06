"""
Career OS — Graph Engine (NetworkX Backend)
In-memory Knowledge Graph with Cypher-like query interface.
"""

from __future__ import annotations
import json
import networkx as nx
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from engine.schemas_graph import (
    BaseNode, BaseEdge, NodeType, EdgeType,
    NodeModel, EdgeModel,
    NODE_REGISTRY, EDGE_REGISTRY,
    CandidateNode, CompanyNode, RoleNode, ProjectNode,
    BulletPointNode, SkillNode, ToolNode, MetricNode,
    CareerDNANode, JobPostingNode, RequirementNode,
    CaseNode, STARStoryNode,
    create_node, create_edge, get_node_type, get_edge_type,
)


@dataclass
class QueryResult:
    """Result of a Cypher-like query."""
    records: List[Dict[str, Any]]
    summary: str = ""


class GraphEngine:
    """
    Knowledge Graph Engine using NetworkX as backend.
    Provides Cypher-like query interface for graph operations.
    """

    def __init__(self, user_id: str = "kevin_augusto", profile_id: str = "default"):
        self.user_id = user_id
        self.profile_id = profile_id
        self.graph = nx.MultiDiGraph()
        self._node_index: Dict[str, BaseNode] = {}
        self._edge_index: Dict[str, BaseEdge] = {}
        self._type_index: Dict[NodeType, Set[str]] = defaultdict(set)
        self._reverse_edges: Dict[str, List[str]] = defaultdict(list)

    # ============================
    # NODE OPERATIONS
    # ============================

    def add_node(self, node: BaseNode) -> str:
        """Add a node to the graph."""
        if node.id in self._node_index:
            return self.update_node(node)

        # Filter by user/profile
        if node.user_id != self.user_id or node.profile_id != self.profile_id:
            raise ValueError(f"Node user/profile mismatch: {node.user_id}/{node.profile_id} vs {self.user_id}/{self.profile_id}")

        self.graph.add_node(node.id, **node.model_dump())
        self._node_index[node.id] = node
        self._type_index[node.type].add(node.id)
        return node.id

    def get_node(self, node_id: str) -> Optional[BaseNode]:
        """Get a node by ID."""
        return self._node_index.get(node_id)

    def update_node(self, node: BaseNode) -> str:
        """Update an existing node."""
        if node.id not in self._node_index:
            return self.add_node(node)

        node.updated_at = datetime.now().isoformat()
        self.graph.nodes[node.id].update(node.model_dump())
        self._node_index[node.id] = node
        return node.id

    def delete_node(self, node_id: str) -> bool:
        """Delete a node and its edges."""
        if node_id not in self._node_index:
            return False

        node = self._node_index[node_id]
        self._type_index[node.type].discard(node_id)
        self.graph.remove_node(node_id)
        del self._node_index[node_id]
        return True

    def get_nodes_by_type(self, node_type: NodeType) -> List[BaseNode]:
        """Get all nodes of a specific type."""
        return [self._node_index[nid] for nid in self._type_index.get(node_type, set())]

    def get_all_nodes(self) -> List[BaseNode]:
        """Get all nodes."""
        return list(self._node_index.values())

    # ============================
    # EDGE OPERATIONS
    # ============================

    def add_edge(self, edge: BaseEdge) -> str:
        """Add an edge to the graph."""
        if edge.id in self._edge_index:
            return edge.id

        # Verify source and target exist
        if edge.source_id not in self._node_index:
            raise ValueError(f"Source node {edge.source_id} not found")
        if edge.target_id not in self._node_index:
            raise ValueError(f"Target node {edge.target_id} not found")

        # Filter by user/profile
        if edge.user_id != self.user_id or edge.profile_id != self.profile_id:
            raise ValueError(f"Edge user/profile mismatch")

        self.graph.add_edge(edge.source_id, edge.target_id, key=edge.id, **edge.model_dump())
        self._edge_index[edge.id] = edge
        self._reverse_edges[edge.target_id].append(edge.id)
        return edge.id

    def get_edge(self, edge_id: str) -> Optional[BaseEdge]:
        """Get an edge by ID."""
        return self._edge_index.get(edge_id)

    def get_edges_by_type(self, edge_type: EdgeType) -> List[BaseEdge]:
        """Get all edges of a specific type."""
        return [e for e in self._edge_index.values() if e.type == edge_type]

    def get_outgoing_edges(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[BaseEdge]:
        """Get outgoing edges from a node."""
        edges = []
        for _, _, key, data in self.graph.out_edges(node_id, keys=True, data=True):
            edge = self._edge_index.get(key)
            if edge and (edge_type is None or edge.type == edge_type):
                edges.append(edge)
        return edges

    def get_incoming_edges(self, node_id: str, edge_type: Optional[EdgeType] = None) -> List[BaseEdge]:
        """Get incoming edges to a node."""
        edges = []
        for _, _, key, data in self.graph.in_edges(node_id, keys=True, data=True):
            edge = self._edge_index.get(key)
            if edge and (edge_type is None or edge.type == edge_type):
                edges.append(edge)
        return edges

    def get_neighbors(self, node_id: str, edge_type: Optional[EdgeType] = None, direction: str = "out") -> List[BaseNode]:
        """Get neighbor nodes connected by edges."""
        if direction == "out":
            edges = self.get_outgoing_edges(node_id, edge_type)
            return [self._node_index[e.target_id] for e in edges if e.target_id in self._node_index]
        else:
            edges = self.get_incoming_edges(node_id, edge_type)
            return [self._node_index[e.source_id] for e in edges if e.source_id in self._node_index]

    # ============================
    # CYPHER-LIKE QUERY INTERFACE
    # ============================

    def match(
        self,
        node_type: Optional[NodeType] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> List[BaseNode]:
        """MATCH clause - find nodes by type and properties."""
        candidates = self.get_nodes_by_type(node_type) if node_type else self.get_all_nodes()

        if filters:
            filtered = []
            for node in candidates:
                match = True
                for key, value in filters.items():
                    node_value = getattr(node, key, None)
                    if node_value != value:
                        match = False
                        break
                if match:
                    filtered.append(node)
            candidates = filtered

        if limit:
            candidates = candidates[:limit]

        return candidates

    def where(self, nodes: List[BaseNode], condition: Callable[[BaseNode], bool]) -> List[BaseNode]:
        """WHERE clause - filter nodes by custom condition."""
        return [n for n in nodes if condition(n)]

    def traverse(
        self,
        start_nodes: List[BaseNode],
        edge_type: EdgeType,
        direction: str = "out",
        max_depth: int = 1,
        target_type: Optional[NodeType] = None
    ) -> List[Tuple[List[BaseNode], List[BaseEdge]]]:
        """
        Traverse graph from start nodes following edge_type.
        Returns list of (path_nodes, path_edges) tuples.
        """
        paths = []
        for start in start_nodes:
            self._dfs_traverse(start.id, edge_type, direction, max_depth, target_type, [], [], paths)
        return paths

    def _dfs_traverse(
        self,
        current_id: str,
        edge_type: EdgeType,
        direction: str,
        max_depth: int,
        target_type: Optional[NodeType],
        path_nodes: List[BaseNode],
        path_edges: List[BaseEdge],
        paths: List[Tuple[List[BaseNode], List[BaseEdge]]]
    ):
        """DFS helper for traverse."""
        if max_depth < 0:
            return

        current_node = self._node_index.get(current_id)
        if not current_node:
            return

        new_path_nodes = path_nodes + [current_node]
        if target_type is None or current_node.type == target_type:
            paths.append((new_path_nodes, path_edges.copy()))

        if max_depth == 0:
            return

        if direction == "out":
            edges = self.get_outgoing_edges(current_id, edge_type)
            next_ids = [e.target_id for e in edges]
        else:
            edges = self.get_incoming_edges(current_id, edge_type)
            next_ids = [e.source_id for e in edges]

        for edge, next_id in zip(edges, next_ids):
            self._dfs_traverse(
                next_id, edge_type, direction, max_depth - 1,
                target_type, new_path_nodes, path_edges + [edge], paths
            )

    def return_records(
        self,
        paths: List[Tuple[List[BaseNode], List[BaseEdge]]],
        projections: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        RETURN clause - project path data into records.
        projections: {"alias": "node.property" or "edge.property"}
        """
        records = []
        for path_nodes, path_edges in paths:
            record = {}
            for alias, expr in projections.items():
                # Simple projection: "node.property" or "edge.property"
                # For now, project from last node/edge in path
                if expr.startswith("node."):
                    prop = expr[5:]
                    if path_nodes:
                        record[alias] = getattr(path_nodes[-1], prop, None)
                elif expr.startswith("edge."):
                    prop = expr[5:]
                    if path_edges:
                        record[alias] = getattr(path_edges[-1], prop, None)
                elif expr == "path_length":
                    record[alias] = len(path_nodes)
            records.append(record)
        return records

    # ============================
    # HIGH-LEVEL QUERY HELPERS
    # ============================

    def find_candidate(self, candidate_id: str = "kevin_augusto") -> Optional[CandidateNode]:
        """Find candidate by ID."""
        candidates = self.match(NodeType.CANDIDATE, {"id": candidate_id})
        return candidates[0] if candidates else None

    def get_candidate_roles(self, candidate_id: str) -> List[RoleNode]:
        """Get all roles for a candidate."""
        candidate = self.get_node(candidate_id)
        if not candidate:
            return []
        return self.get_neighbors(candidate_id, EdgeType.WORKED_AS, "out")

    def get_role_company(self, role_id: str) -> Optional[CompanyNode]:
        """Get company for a role."""
        companies = self.get_neighbors(role_id, EdgeType.AT_COMPANY, "out")
        return companies[0] if companies else None

    def get_role_achievements(self, role_id: str) -> List[BulletPointNode]:
        """Get bullet points for a role."""
        return self.get_neighbors(role_id, EdgeType.HAS_ACHIEVEMENT, "out")

    def get_bullet_skills(self, bullet_id: str) -> List[SkillNode]:
        """Get skills demonstrated by a bullet point."""
        return self.get_neighbors(bullet_id, EdgeType.DEMONSTRATES, "out")

    def get_bullet_tools(self, bullet_id: str) -> List[ToolNode]:
        """Get tools utilized by a bullet point."""
        return self.get_neighbors(bullet_id, EdgeType.UTILIZED, "out")

    def get_bullet_metrics(self, bullet_id: str) -> List[MetricNode]:
        """Get metrics produced by a bullet point."""
        return self.get_neighbors(bullet_id, EdgeType.PRODUCED_IMPACT, "out")

    def get_skill_hierarchy(self, skill_id: str, direction: str = "up") -> List[SkillNode]:
        """Get skill hierarchy (parents or children)."""
        edge_type = EdgeType.SUBSET_OF
        if direction == "up":
            # skill -> SUBSET_OF -> parent_skill
            return self.get_neighbors(skill_id, edge_type, "out")
        else:
            # child_skill -> SUBSET_OF -> skill
            return self.get_neighbors(skill_id, edge_type, "in")

    def get_related_skills(self, skill_id: str) -> List[SkillNode]:
        """Get semantically related skills."""
        return self.get_neighbors(skill_id, EdgeType.RELATED_TO, "out")

    def find_job_requirements(self, job_id: str) -> List[RequirementNode]:
        """Get requirements for a job posting."""
        return self.get_neighbors(job_id, EdgeType.REQUIRES, "out")

    def get_requirement_skills(self, req_id: str) -> List[SkillNode]:
        """Get skills mapped to a requirement."""
        return self.get_neighbors(req_id, EdgeType.MAPS_TO_SKILL, "out")

    def get_requirement_tools(self, req_id: str) -> List[ToolNode]:
        """Get tools mapped to a requirement."""
        return self.get_neighbors(req_id, EdgeType.MAPS_TO_TOOL, "out")

    # ============================
    # MATCH SCORE & GAP ANALYSIS
    # ============================

    def calculate_match_score(self, candidate_id: str, job_id: str) -> Dict[str, Any]:
        """
        Calculate deterministic match score using Jaccard similarity.
        Returns: {match_score, total_reqs, matched_reqs, missing_skills, missing_tools}
        """
        # Get all requirements for the job
        requirements = self.find_job_requirements(job_id)
        if not requirements:
            return {"match_score": 0.0, "total_reqs": 0, "matched_reqs": 0, "missing_skills": [], "missing_tools": []}

        # Collect all required assets (skills + tools)
        required_skills = set()
        required_tools = set()
        req_details = []

        for req in requirements:
            skills = self.get_requirement_skills(req.id)
            tools = self.get_requirement_tools(req.id)
            for s in skills:
                required_skills.add(s.name.lower())
            for t in tools:
                required_tools.add(t.name.lower())
            req_details.append({
                "requirement": req.description,
                "skills": [s.name for s in skills],
                "tools": [t.name for t in tools],
                "weight": req.importance_weight
            })

        # Collect candidate assets
        candidate_skills = set()
        candidate_tools = set()

        roles = self.get_candidate_roles(candidate_id)
        for role in roles:
            bullets = self.get_role_achievements(role.id)
            for bullet in bullets:
                for skill in self.get_bullet_skills(bullet.id):
                    candidate_skills.add(skill.name.lower())
                for tool in self.get_bullet_tools(bullet.id):
                    candidate_tools.add(tool.name.lower())

        # Calculate matches
        matched_skills = required_skills & candidate_skills
        matched_tools = required_tools & candidate_tools
        matched_total = len(matched_skills) + len(matched_tools)
        required_total = len(required_skills) + len(required_tools)

        match_score = (matched_total / required_total * 100) if required_total > 0 else 0.0

        missing_skills = list(required_skills - candidate_skills)
        missing_tools = list(required_tools - candidate_tools)

        return {
            "match_score": round(match_score, 2),
            "total_reqs": required_total,
            "matched_reqs": matched_total,
            "matched_skills": list(matched_skills),
            "matched_tools": list(matched_tools),
            "missing_skills": missing_skills,
            "missing_tools": missing_tools,
            "requirement_details": req_details
        }

    def get_relevant_bullets_for_job(self, candidate_id: str, job_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Rank bullet points by relevance to job requirements."""
        # Get required skills/tools for job
        requirements = self.find_job_requirements(job_id)
        required_skills = set()
        required_tools = set()
        for req in requirements:
            for s in self.get_requirement_skills(req.id):
                required_skills.add(s.name.lower())
            for t in self.get_requirement_tools(req.id):
                required_tools.add(t.name.lower())

        # Score each bullet
        scored_bullets = []
        roles = self.get_candidate_roles(candidate_id)
        for role in roles:
            bullets = self.get_role_achievements(role.id)
            for bullet in bullets:
                bullet_skills = {s.name.lower() for s in self.get_bullet_skills(bullet.id)}
                bullet_tools = {t.name.lower() for t in self.get_bullet_tools(bullet.id)}

                skill_matches = len(bullet_skills & required_skills)
                tool_matches = len(bullet_tools & required_tools)
                total_matches = skill_matches + tool_matches

                if total_matches > 0:
                    scored_bullets.append({
                        "role": role.title_pt,
                        "company": self.get_role_company(role.id).name if self.get_role_company(role.id) else "",
                        "bullet": bullet.text_pt,
                        "bullet_en": bullet.text_en,
                        "skill_matches": skill_matches,
                        "tool_matches": tool_matches,
                        "total_matches": total_matches,
                        "matched_skills": list(bullet_skills & required_skills),
                        "matched_tools": list(bullet_tools & required_tools),
                        "impact_value": bullet.impact_value,
                        "quantifiable_metric": bullet.quantifiable_metric
                    })

        # Sort by relevance
        scored_bullets.sort(key=lambda x: (x["total_matches"], x["impact_value"]), reverse=True)
        return scored_bullets[:limit]

    # ============================
    # GRAPHRAG: SUBGRAPH RETRIEVAL
    # ============================

    def get_subgraph_for_job(self, job_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """
        Retrieve relevant subgraph for a job posting (GraphRAG context).
        Returns nodes and edges relevant to job requirements.
        """
        job = self.get_node(job_id)
        if not job or job.type != NodeType.JOB_POSTING:
            return {"nodes": [], "edges": []}

        requirements = self.find_job_requirements(job_id)
        relevant_node_ids = set()
        relevant_edge_ids = set()

        # Add job and requirements
        relevant_node_ids.add(job_id)
        for req in requirements:
            relevant_node_ids.add(req.id)
            # Add edges from job to requirements
            for edge in self.get_outgoing_edges(job_id, EdgeType.REQUIRES):
                if edge.target_id == req.id:
                    relevant_edge_ids.add(edge.id)

            # Add mapped skills/tools
            for skill in self.get_requirement_skills(req.id):
                relevant_node_ids.add(skill.id)
                for edge in self.get_outgoing_edges(req.id, EdgeType.MAPS_TO_SKILL):
                    if edge.target_id == skill.id:
                        relevant_edge_ids.add(edge.id)

            for tool in self.get_requirement_tools(req.id):
                relevant_node_ids.add(tool.id)
                for edge in self.get_outgoing_edges(req.id, EdgeType.MAPS_TO_TOOL):
                    if edge.target_id == tool.id:
                        relevant_edge_ids.add(edge.id)

        # Find candidate bullets that match
        candidate = self.find_candidate()
        if candidate:
            roles = self.get_candidate_roles(candidate.id)
            for role in roles:
                relevant_node_ids.add(role.id)
                # Add WORKED_AS edge
                for edge in self.get_outgoing_edges(candidate.id, EdgeType.WORKED_AS):
                    if edge.target_id == role.id:
                        relevant_edge_ids.add(edge.id)

                company = self.get_role_company(role.id)
                if company:
                    relevant_node_ids.add(company.id)
                    for edge in self.get_outgoing_edges(role.id, EdgeType.AT_COMPANY):
                        if edge.target_id == company.id:
                            relevant_edge_ids.add(edge.id)

                bullets = self.get_role_achievements(role.id)
                for bullet in bullets:
                    bullet_skills = {s.name.lower() for s in self.get_bullet_skills(bullet.id)}
                    bullet_tools = {t.name.lower() for t in self.get_bullet_tools(bullet.id)}

                    req_skills = set()
                    req_tools = set()
                    for req in requirements:
                        req_skills.update(s.name.lower() for s in self.get_requirement_skills(req.id))
                        req_tools.update(t.name.lower() for t in self.get_requirement_tools(req.id))

                    if bullet_skills & req_skills or bullet_tools & req_tools:
                        relevant_node_ids.add(bullet.id)
                        for edge in self.get_outgoing_edges(role.id, EdgeType.HAS_ACHIEVEMENT):
                            if edge.target_id == bullet.id:
                                relevant_edge_ids.add(edge.id)

                        # Add connected skills/tools/metrics
                        for skill in self.get_bullet_skills(bullet.id):
                            relevant_node_ids.add(skill.id)
                            for edge in self.get_outgoing_edges(bullet.id, EdgeType.DEMONSTRATES):
                                if edge.target_id == skill.id:
                                    relevant_edge_ids.add(edge.id)

                        for tool in self.get_bullet_tools(bullet.id):
                            relevant_node_ids.add(tool.id)
                            for edge in self.get_outgoing_edges(bullet.id, EdgeType.UTILIZED):
                                if edge.target_id == tool.id:
                                    relevant_edge_ids.add(edge.id)

                        for metric in self.get_bullet_metrics(bullet.id):
                            relevant_node_ids.add(metric.id)
                            for edge in self.get_outgoing_edges(bullet.id, EdgeType.PRODUCED_IMPACT):
                                if edge.target_id == metric.id:
                                    relevant_edge_ids.add(edge.id)

        # Build subgraph
        nodes = [self._node_index[nid].model_dump() for nid in relevant_node_ids if nid in self._node_index]
        edges = [self._edge_index[eid].model_dump() for eid in relevant_edge_ids if eid in self._edge_index]

        return {"nodes": nodes, "edges": edges}

    # ============================
    # EXPORT / IMPORT
    # ============================

    def to_json(self) -> Dict[str, Any]:
        """Export graph to JSON."""
        return {
            "user_id": self.user_id,
            "profile_id": self.profile_id,
            "nodes": [node.model_dump() for node in self._node_index.values()],
            "edges": [edge.model_dump() for edge in self._edge_index.values()],
            "exported_at": datetime.now().isoformat()
        }

    def save_json(self, filepath: str):
        """Save graph to JSON file."""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, ensure_ascii=False, indent=2)

    def load_json(self, filepath: str):
        """Load graph from JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.user_id = data.get("user_id", self.user_id)
        self.profile_id = data.get("profile_id", self.profile_id)

        # Clear existing
        self.graph.clear()
        self._node_index.clear()
        self._edge_index.clear()
        self._type_index.clear()
        self._reverse_edges.clear()

        # Load nodes
        for node_data in data.get("nodes", []):
            node_type = NodeType(node_data["type"])
            model_class = NODE_REGISTRY.get(node_type)
            if model_class:
                node = model_class(**node_data)
                self.add_node(node)

        # Load edges
        for edge_data in data.get("edges", []):
            edge_type = EdgeType(edge_data["type"])
            model_class = EDGE_REGISTRY.get(edge_type)
            if model_class:
                edge = model_class(**edge_data)
                self.add_edge(edge)

    # ============================
    # STATS & DEBUG
    # ============================

    def stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        node_counts = {nt.value: len(ids) for nt, ids in self._type_index.items()}
        edge_counts = defaultdict(int)
        for edge in self._edge_index.values():
            edge_counts[edge.type.value] += 1

        return {
            "total_nodes": len(self._node_index),
            "total_edges": len(self._edge_index),
            "node_types": node_counts,
            "edge_types": dict(edge_counts),
            "user_id": self.user_id,
            "profile_id": self.profile_id
        }

    def print_stats(self):
        """Pretty print graph statistics."""
        stats = self.stats()
        print(f"\n=== Graph Stats ({self.user_id}/{self.profile_id}) ===")
        print(f"Total Nodes: {stats['total_nodes']}")
        print(f"Total Edges: {stats['total_edges']}")
        print("\nNode Types:")
        for nt, count in stats["node_types"].items():
            print(f"  {nt}: {count}")
        print("\nEdge Types:")
        for et, count in stats["edge_types"].items():
            print(f"  {et}: {count}")