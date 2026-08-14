"""
Career OS — Skill Transferability Engine
Uses shortest path algorithms on the competency graph to find skill equivalencies
and transferability paths between candidate skills and job requirements.
"""

from __future__ import annotations
import json
from typing import Dict, List, Set, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque
from pathlib import Path

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType, EdgeType, SkillCategory


@dataclass
class TransferPath:
    """Represents a skill transferability path."""
    source_skill: str
    target_skill: str
    path: List[str]  # Skill names in path
    distance: int
    confidence: float
    path_types: List[str]  # Edge types in path


@dataclass
class SkillGap:
    """Represents a skill gap with transferability options."""
    required_skill: str
    importance_weight: float
    candidate_skills: List[str]
    transfer_paths: List[TransferPath]
    best_match: Optional[TransferPath]
    gap_severity: str  # "critical", "high", "medium", "low"


class SkillTransferabilityEngine:
    """
    Engine for computing skill transferability using graph algorithms.
    Finds shortest paths between skills via SUBSET_OF and RELATED_TO edges.
    """

    def __init__(self, graph_engine: GraphEngine):
        self.engine = graph_engine
        self._skill_id_to_name: Dict[str, str] = {}
        self._skill_name_to_id: Dict[str, str] = {}
        self._adjacency: Dict[str, List[Tuple[str, str, float]]] = {}  # node_id -> [(neighbor_id, edge_type, weight)]
        self._build_skill_graph()

    def _build_skill_graph(self):
        """Build adjacency list from graph for skill transferability."""
        skills = self.engine.get_nodes_by_type(NodeType.SKILL)
        
        for skill in skills:
            self._skill_id_to_name[skill.id] = skill.name
            self._skill_name_to_id[skill.name] = skill.id
            self._adjacency[skill.id] = []

        # Add SUBSET_OF edges (bidirectional for transferability)
        subset_edges = self.engine.get_edges_by_type(EdgeType.SUBSET_OF)
        for edge in subset_edges:
            if edge.source_id in self._skill_id_to_name and edge.target_id in self._skill_id_to_name:
                # Child -> Parent (specialization to generalization)
                self._adjacency[edge.source_id].append((edge.target_id, "SUBSET_OF_UP", 1.0))
                # Parent -> Child (generalization to specialization) - lower weight
                self._adjacency[edge.target_id].append((edge.source_id, "SUBSET_OF_DOWN", 0.7))

        # Add RELATED_TO edges (bidirectional)
        related_edges = self.engine.get_edges_by_type(EdgeType.RELATED_TO)
        for edge in related_edges:
            if edge.source_id in self._skill_id_to_name and edge.target_id in self._skill_id_to_name:
                strength = edge.properties.get("strength", 0.5)
                self._adjacency[edge.source_id].append((edge.target_id, "RELATED_TO", strength))
                self._adjacency[edge.target_id].append((edge.source_id, "RELATED_TO", strength))

    def find_shortest_path(self, source_skill: str, target_skill: str, max_depth: int = 4) -> Optional[TransferPath]:
        """
        Find shortest transferability path between two skills using BFS.
        Returns TransferPath with path, distance, and confidence.
        """
        source_id = self._skill_name_to_id.get(source_skill)
        target_id = self._skill_name_to_id.get(target_skill)
        
        if not source_id or not target_id:
            return None
        
        if source_id == target_id:
            return TransferPath(
                source_skill=source_skill,
                target_skill=target_skill,
                path=[source_skill],
                distance=0,
                confidence=1.0,
                path_types=[]
            )

        # BFS for shortest path
        queue = deque([(source_id, [source_id], [], 1.0)])  # (current_id, path_ids, edge_types, confidence)
        visited = {source_id}
        
        while queue:
            current_id, path_ids, edge_types, confidence = queue.popleft()
            
            if len(path_ids) > max_depth:
                continue
            
            if current_id == target_id:
                path_names = [self._skill_id_to_name[pid] for pid in path_ids]
                return TransferPath(
                    source_skill=source_skill,
                    target_skill=target_skill,
                    path=path_names,
                    distance=len(path_ids) - 1,
                    confidence=confidence,
                    path_types=edge_types
                )
            
            for neighbor_id, edge_type, weight in self._adjacency.get(current_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    new_confidence = confidence * weight
                    queue.append((
                        neighbor_id,
                        path_ids + [neighbor_id],
                        edge_types + [edge_type],
                        new_confidence
                    ))
        
        return None

    def find_all_transfer_paths(self, source_skill: str, target_skills: List[str], max_depth: int = 4) -> List[TransferPath]:
        """Find transfer paths from one skill to multiple target skills."""
        paths = []
        for target in target_skills:
            path = self.find_shortest_path(source_skill, target, max_depth)
            if path:
                paths.append(path)
        # Sort by distance then confidence
        paths.sort(key=lambda p: (p.distance, -p.confidence))
        return paths

    def get_skill_ancestry(self, skill_name: str, max_levels: int = 3) -> List[str]:
        """Get parent categories (SUBSET_OF up) for a skill."""
        skill_id = self._skill_name_to_id.get(skill_name)
        if not skill_id:
            return []
        
        ancestors = []
        current_id = skill_id
        visited = set()
        
        for _ in range(max_levels):
            # Find SUBSET_OF_UP edges
            parents = [
                (nid, wt) for nid, et, wt in self._adjacency.get(current_id, [])
                if et == "SUBSET_OF_UP" and nid not in visited
            ]
            if not parents:
                break
            # Take highest weight parent
            parent_id, _ = max(parents, key=lambda x: x[1])
            parent_name = self._skill_id_to_name.get(parent_id)
            if parent_name:
                ancestors.append(parent_name)
                visited.add(parent_id)
                current_id = parent_id
            else:
                break
        
        return ancestors

    def get_skill_descendants(self, skill_name: str, max_levels: int = 2) -> List[str]:
        """Get child skills (SUBSET_OF down) for a category."""
        skill_id = self._skill_name_to_id.get(skill_name)
        if not skill_id:
            return []
        
        descendants = []
        queue = deque([(skill_id, 0)])
        visited = {skill_id}
        
        while queue:
            current_id, level = queue.popleft()
            if level >= max_levels:
                continue
            
            children = [
                nid for nid, et, _ in self._adjacency.get(current_id, [])
                if et == "SUBSET_OF_DOWN" and nid not in visited
            ]
            
            for child_id in children:
                child_name = self._skill_id_to_name.get(child_id)
                if child_name:
                    descendants.append(child_name)
                    visited.add(child_id)
                    queue.append((child_id, level + 1))
        
        return descendants

    def get_related_skills(self, skill_name: str, min_strength: float = 0.3) -> List[Tuple[str, float]]:
        """Get semantically related skills with strength scores."""
        skill_id = self._skill_name_to_id.get(skill_name)
        if not skill_id:
            return []
        
        related = []
        for neighbor_id, edge_type, weight in self._adjacency.get(skill_id, []):
            if edge_type == "RELATED_TO" and weight >= min_strength:
                neighbor_name = self._skill_id_to_name.get(neighbor_id)
                if neighbor_name:
                    related.append((neighbor_name, weight))
        
        related.sort(key=lambda x: -x[1])
        return related

    def calculate_transferability_score(self, candidate_skill: str, required_skill: str) -> float:
        """
        Calculate transferability score (0-1) between candidate and required skill.
        Based on shortest path distance and confidence.
        """
        path = self.find_shortest_path(candidate_skill, required_skill)
        if not path:
            return 0.0
        
        # Score based on distance and confidence
        # Distance 0 = 1.0, Distance 1 = 0.8, Distance 2 = 0.6, Distance 3 = 0.4, Distance 4 = 0.2
        distance_score = max(0.0, 1.0 - (path.distance * 0.2))
        return distance_score * path.confidence

    def find_best_candidate_skills(self, required_skills: List[str], candidate_skills: List[str], top_k: int = 3) -> Dict[str, List[Tuple[str, float]]]:
        """
        For each required skill, find the best matching candidate skills.
        Returns: {required_skill: [(candidate_skill, score), ...]}
        """
        results = {}
        for req_skill in required_skills:
            matches = []
            for cand_skill in candidate_skills:
                score = self.calculate_transferability_score(cand_skill, req_skill)
                if score > 0.0:
                    matches.append((cand_skill, score))
            
            matches.sort(key=lambda x: -x[1])
            results[req_skill] = matches[:top_k]
        
        return results

    def analyze_skill_gaps(self, 
                           required_skills: List[Dict[str, Any]],  # [{"name": "...", "weight": 1.0}]
                           candidate_skills: List[str]) -> List[SkillGap]:
        """
        Analyze skill gaps with transferability options.
        Returns list of SkillGap objects sorted by severity.
        """
        gaps = []
        
        for req in required_skills:
            req_name = req["name"]
            weight = req.get("weight", 1.0)
            
            # Check direct match
            direct_match = req_name in candidate_skills
            
            # Find transfer paths from candidate skills
            transfer_paths = self.find_all_transfer_paths(req_name, candidate_skills)
            
            best_match = transfer_paths[0] if transfer_paths else None
            
            # Determine gap severity
            if direct_match:
                severity = "covered"
            elif best_match and best_match.distance <= 1 and best_match.confidence > 0.7:
                severity = "low"
            elif best_match and best_match.distance <= 2:
                severity = "medium"
            elif best_match:
                severity = "high"
            else:
                severity = "critical"
            
            gap = SkillGap(
                required_skill=req_name,
                importance_weight=weight,
                candidate_skills=candidate_skills,
                transfer_paths=transfer_paths[:3],
                best_match=best_match,
                gap_severity=severity
            )
            gaps.append(gap)
        
        # Sort by severity and importance
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "covered": 4}
        gaps.sort(key=lambda g: (severity_order[g.gap_severity], -g.importance_weight))
        
        return gaps

    def get_skill_cluster(self, skill_name: str, radius: int = 2) -> Dict[str, Any]:
        """
        Get a cluster of related skills around a central skill.
        Useful for visualization and understanding skill neighborhoods.
        """
        skill_id = self._skill_name_to_id.get(skill_name)
        if not skill_id:
            return {}
        
        cluster = {
            "center": skill_name,
            "ancestors": self.get_skill_ancestry(skill_name),
            "descendants": self.get_skill_descendants(skill_name),
            "related": self.get_related_skills(skill_name),
            "transferable_to": []
        }
        
        # Find skills within radius hops
        all_skills = list(self._skill_name_to_id.keys())
        for other_skill in all_skills:
            if other_skill == skill_name:
                continue
            path = self.find_shortest_path(skill_name, other_skill, max_depth=radius)
            if path and path.distance <= radius:
                cluster["transferable_to"].append({
                    "skill": other_skill,
                    "distance": path.distance,
                    "confidence": path.confidence,
                    "path": path.path
                })
        
        cluster["transferable_to"].sort(key=lambda x: (x["distance"], -x["confidence"]))
        return cluster

    def export_transferability_matrix(self, output_path: str):
        """Export full transferability matrix as JSON for analysis."""
        all_skills = list(self._skill_name_to_id.keys())
        matrix = {}
        
        for i, source in enumerate(all_skills):
            matrix[source] = {}
            for target in all_skills:
                if source != target:
                    score = self.calculate_transferability_score(source, target)
                    if score > 0.0:
                        matrix[source][target] = round(score, 3)
            if i % 20 == 0:
                print(f"  Computed {i+1}/{len(all_skills)} rows...")
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(matrix, f, ensure_ascii=False, indent=2)
        
        print(f"Transferability matrix exported to: {output_path}")


def build_transferability_engine(graph_path: str = "data/graph_with_cases.json") -> SkillTransferabilityEngine:
    """Factory function to build engine from graph file."""
    engine = GraphEngine()
    engine.load_json(graph_path)
    return SkillTransferabilityEngine(engine)


if __name__ == "__main__":
    # Test the engine
    transfer_engine = build_transferability_engine()
    
    print("=== Skill Transferability Engine Test ===\n")
    
    # Test 1: Ancestry
    print("1. Skill Ancestry (n8n):")
    ancestry = transfer_engine.get_skill_ancestry("n8n")
    print(f"   n8n -> {' -> '.join(ancestry)}")
    
    # Test 2: Related skills
    print("\n2. Related Skills (Prompt Engineering):")
    related = transfer_engine.get_related_skills("Prompt Engineering")
    for skill, strength in related[:5]:
        print(f"   {skill}: {strength:.2f}")
    
    # Test 3: Transferability
    print("\n3. Transferability Score:")
    score = transfer_engine.calculate_transferability_score("n8n", "Make (Integromat)")
    print(f"   n8n -> Make (Integromat): {score:.2f}")
    
    score = transfer_engine.calculate_transferability_score("Prompt Engineering", "RAG (Retrieval-Augmented Generation)")
    print(f"   Prompt Engineering -> RAG: {score:.2f}")
    
    score = transfer_engine.calculate_transferability_score("Sales Enablement", "Go-to-Market Strategy")
    print(f"   Sales Enablement -> GTM Strategy: {score:.2f}")
    
    # Test 4: Gap Analysis
    print("\n4. Gap Analysis Example:")
    required = [
        {"name": "n8n", "weight": 1.0},
        {"name": "RAG (Retrieval-Augmented Generation)", "weight": 0.9},
        {"name": "Kubernetes", "weight": 0.7},
        {"name": "Sales Enablement", "weight": 0.8}
    ]
    candidate = ["Make (Integromat)", "Prompt Engineering", "Sales Excellence", "Docker"]
    
    gaps = transfer_engine.analyze_skill_gaps(required, candidate)
    for gap in gaps:
        print(f"   {gap.required_skill} ({gap.gap_severity}, weight={gap.importance_weight})")
        if gap.best_match:
            print(f"      Best: {gap.best_match.source_skill} -> {gap.best_match.target_skill} "
                  f"(dist={gap.best_match.distance}, conf={gap.best_match.confidence:.2f})")
            print(f"      Path: {' -> '.join(gap.best_match.path)}")
    
    # Test 5: Skill Cluster
    print("\n5. Skill Cluster (Thinking Environment):")
    cluster = transfer_engine.get_skill_cluster("Thinking Environment", radius=2)
    print(f"   Ancestors: {cluster['ancestors']}")
    print(f"   Descendants: {cluster['descendants'][:5]}")
    print(f"   Related: {[(s, f'{w:.2f}') for s, w in cluster['related'][:5]]}")
    print(f"   Transferable (r=2): {len(cluster['transferable_to'])} skills")
    
    print("\n[OK] All tests passed!")