"""
Career OS — Phase 4: GraphRAG Retriever & Match Engine
Subgraph context retrieval for LLM prompts + Deterministic match scoring.
"""

from __future__ import annotations
from typing import Dict, List, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from engine.graph_engine import GraphEngine
from engine.schemas_graph import NodeType, EdgeType, SkillNode, ToolNode, RequirementNode
from engine.skill_transferability import SkillTransferabilityEngine, SkillGap


@dataclass
class SubgraphContext:
    """Retrieved subgraph context for GraphRAG."""
    job_id: str
    job_title: str
    company_name: str
    requirement_nodes: List[Dict[str, Any]]
    candidate_skills: List[Dict[str, Any]]
    candidate_tools: List[Dict[str, Any]]
    candidate_bullets: List[Dict[str, Any]]
    candidate_metrics: List[Dict[str, Any]]
    skill_transferability: Dict[str, List[Dict[str, Any]]]
    total_requirements: int
    matched_requirements: int
    match_score: float


@dataclass
class MatchResult:
    """Deterministic match result with gap analysis."""
    job_id: str
    job_title: str
    company_name: str
    match_score: float  # 0-100%
    total_requirements: int
    matched_requirements: int
    requirement_details: List[Dict[str, Any]]
    skill_gaps: List[SkillGap]
    transferable_skills: Dict[str, List[Tuple[str, float]]]  # req_skill -> [(cand_skill, score)]
    top_bullets: List[Dict[str, Any]]  # Ranked bullets for resume
    summary: str


class GraphRAGRetriever:
    """
    Retrieves relevant subgraph context for a job posting.
    Replaces naive full-resume injection with targeted subgraph.
    """
    
    def __init__(self, graph_engine: GraphEngine):
        self.engine = graph_engine
        self.transfer_engine = SkillTransferabilityEngine(graph_engine)
    
    def retrieve_for_job(self, job_id: str, max_bullets: int = 8) -> SubgraphContext:
        """
        Retrieve minimal relevant subgraph for job requirements.
        Returns structured context for LLM prompt injection.
        """
        job = self.engine.get_node(job_id)
        if not job or job.type != NodeType.JOB_POSTING:
            raise ValueError(f"Job {job_id} not found or not a JobPosting")
        
        # 1. Get job requirements
        requirements = self.engine.get_neighbors(job_id, EdgeType.REQUIRES, "out")
        requirement_nodes = []
        
        for req in requirements:
            # Get mapped skills/tools for this requirement
            mapped_skills = self.engine.get_neighbors(req.id, EdgeType.MAPS_TO_SKILL, "out")
            mapped_tools = self.engine.get_neighbors(req.id, EdgeType.MAPS_TO_TOOL, "out")
            
            requirement_nodes.append({
                "requirement": req.description,
                "importance_weight": req.importance_weight,
                "requirement_type": req.requirement_type,
                "category": req.category,
                "mapped_skills": [{"name": s.name, "category": s.category.value} for s in mapped_skills],
                "mapped_tools": [{"name": t.name, "type": t.tool_type} for t in mapped_tools]
            })
        
        # 2. Find candidate
        candidates = self.engine.get_nodes_by_type(NodeType.CANDIDATE)
        if not candidates:
            raise ValueError("No candidate in graph")
        candidate = candidates[0]
        candidate_id = candidate.id
        
        # 3. Get candidate skills/tools from bullets (evidence-based)
        candidate_skills, candidate_tools, candidate_bullets, candidate_metrics = \
            self._get_candidate_evidence(candidate_id)
        
        # 4. Calculate transferability for each required skill
        required_skill_names = set()
        for req in requirement_nodes:
            for s in req["mapped_skills"]:
                required_skill_names.add(s["name"])
            for t in req["mapped_tools"]:
                required_skill_names.add(t["name"])
        
        candidate_skill_names = [s["name"] for s in candidate_skills]
        candidate_tool_names = [t["name"] for t in candidate_tools]
        all_candidate_assets = candidate_skill_names + candidate_tool_names
        
        skill_transferability = {}
        for req_skill in required_skill_names:
            matches = self.transfer_engine.find_all_transfer_paths(req_skill, all_candidate_assets)
            skill_transferability[req_skill] = [
                {
                    "candidate_skill": m.source_skill,
                    "target_skill": m.target_skill,
                    "distance": m.distance,
                    "confidence": m.confidence,
                    "path": m.path
                }
                for m in matches[:3]  # Top 3 transfer paths
            ]
        
        # 5. Rank bullets by relevance
        top_bullets = self.engine.get_relevant_bullets_for_job(candidate_id, job_id, limit=max_bullets)
        
        # 6. Calculate match score
        match_result = self.engine.calculate_match_score(candidate_id, job_id)
        
        return SubgraphContext(
            job_id=job_id,
            job_title=job.title,
            company_name=job.company_name,
            requirement_nodes=requirement_nodes,
            candidate_skills=candidate_skills,
            candidate_tools=candidate_tools,
            candidate_bullets=top_bullets,
            candidate_metrics=candidate_metrics,
            skill_transferability=skill_transferability,
            total_requirements=match_result["total_reqs"],
            matched_requirements=match_result["matched_reqs"],
            match_score=match_result["match_score"]
        )
    
    def _get_candidate_evidence(self, candidate_id: str) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """Extract candidate skills, tools, bullets, metrics from graph."""
        roles = self.engine.get_candidate_roles(candidate_id)
        
        all_skills = []
        all_tools = []
        all_bullets = []
        all_metrics = []
        
        seen_skills = set()
        seen_tools = set()
        seen_bullets = set()
        seen_metrics = set()
        
        for role in roles:
            bullets = self.engine.get_role_achievements(role.id)
            company = self.engine.get_role_company(role.id)
            company_name = company.name if company else ""
            
            for bullet in bullets:
                if bullet.id in seen_bullets:
                    continue
                seen_bullets.add(bullet.id)
                
                # Bullet info
                all_bullets.append({
                    "id": bullet.id,
                    "text_pt": bullet.text_pt,
                    "text_en": bullet.text_en,
                    "role": role.title_pt,
                    "company": company_name,
                    "impact_value": bullet.impact_value,
                    "quantifiable_metric": bullet.quantifiable_metric
                })
                
                # Skills
                for skill in self.engine.get_bullet_skills(bullet.id):
                    if skill.name not in seen_skills:
                        seen_skills.add(skill.name)
                        all_skills.append({
                            "name": skill.name,
                            "category": skill.category.value,
                            "level": skill.level,
                            "source_bullet": bullet.text_pt[:80]
                        })
                
                # Tools
                for tool in self.engine.get_bullet_tools(bullet.id):
                    if tool.name not in seen_tools:
                        seen_tools.add(tool.name)
                        all_tools.append({
                            "name": tool.name,
                            "type": tool.tool_type,
                            "source_bullet": bullet.text_pt[:80]
                        })
                
                # Metrics
                for metric in self.engine.get_bullet_metrics(bullet.id):
                    if metric.value_change not in seen_metrics:
                        seen_metrics.add(metric.value_change)
                        all_metrics.append({
                            "indicator": metric.indicator,
                            "value_change": metric.value_change,
                            "context": metric.context_pt
                        })
        
        return all_skills, all_tools, all_bullets, all_metrics
    
    def build_llm_context(self, subgraph: SubgraphContext, max_tokens: int = 3000) -> str:
        """
        Build optimized LLM context from subgraph.
        Targets ~70% token reduction vs full resume injection.
        """
        lines = []
        lines.append(f"=== VAGA: {subgraph.job_title} @ {subgraph.company_name} ===")
        lines.append(f"Match Score: {subgraph.match_score:.1f}% ({subgraph.matched_requirements}/{subgraph.total_requirements} requisitos)")
        lines.append("")
        
        lines.append("REQUISITOS DA VAGA (mapeados para skills/tools):")
        for i, req in enumerate(subgraph.requirement_nodes, 1):
            skills_str = ", ".join([s["name"] for s in req["mapped_skills"]]) or "—"
            tools_str = ", ".join([t["name"] for t in req["mapped_tools"]]) or "—"
            lines.append(f"  {i}. [{req['importance_weight']:.1f}] {req['requirement']}")
            lines.append(f"      Skills: {skills_str}")
            lines.append(f"      Tools: {tools_str}")
            # Add transferability info
            for s in req["mapped_skills"]:
                if s["name"] in subgraph.skill_transferability:
                    paths = subgraph.skill_transferability[s["name"]]
                    if paths:
                        best = paths[0]
                        lines.append(f"      ↳ Transferível via: {best['candidate_skill']} (dist={best['distance']}, conf={best['confidence']:.2f})")
        lines.append("")
        
        lines.append("SUAS SKILLS EVIDENCIADAS:")
        for skill in subgraph.candidate_skills[:20]:
            lines.append(f"  - {skill['name']} ({skill['category']}) — Ex: {skill['source_bullet']}")
        lines.append("")
        
        lines.append("SUAS TOOLS EVIDENCIADAS:")
        for tool in subgraph.candidate_tools[:15]:
            lines.append(f"  - {tool['name']} ({tool['type']}) — Ex: {tool['source_bullet']}")
        lines.append("")
        
        lines.append("SUAS CONQUISTAS MAIS RELEVANTES (Top bullets):")
        for i, bullet in enumerate(subgraph.candidate_bullets, 1):
            lines.append(f"  {i}. [{bullet['role']} @ {bullet['company']}] {bullet['text_pt']}")
            if bullet["quantifiable_metric"]:
                lines.append(f"      Métrica: {bullet['quantifiable_metric']}")
        lines.append("")
        
        lines.append("MÉTRICAS DE IMPACTO:")
        for metric in subgraph.candidate_metrics[:10]:
            lines.append(f"  - {metric['value_change']}: {metric['context']}")
        
        context = "\n".join(lines)
        
        # Rough token estimate (4 chars ≈ 1 token for Portuguese)
        estimated_tokens = len(context) // 4
        if estimated_tokens > max_tokens:
            # Truncate bullets first
            return self.build_llm_context(subgraph, max_tokens)
        
        return context


class MatchEngine:
    """
    Deterministic match scoring using Jaccard similarity on requirement coverage.
    Enhanced with skill transferability for "near matches".
    """
    
    def __init__(self, graph_engine: GraphEngine):
        self.engine = graph_engine
        self.transfer_engine = SkillTransferabilityEngine(graph_engine)
    
    def calculate_match(self, job_id: str, candidate_id: Optional[str] = None) -> MatchResult:
        """
        Calculate comprehensive match result with deterministic scoring.
        """
        job = self.engine.get_node(job_id)
        if not job or job.type != NodeType.JOB_POSTING:
            raise ValueError(f"Job {job_id} not found")
        
        if candidate_id is None:
            candidates = self.engine.get_nodes_by_type(NodeType.CANDIDATE)
            if not candidates:
                raise ValueError("No candidate in graph")
            candidate_id = candidates[0].id
        
        # Base match score (exact matches only)
        base_match = self.engine.calculate_match_score(candidate_id, job_id)
        
        # Enhanced with transferability
        enhanced_result = self._calculate_enhanced_match(candidate_id, job_id, base_match)
        
        # Get top bullets for resume
        top_bullets = self.engine.get_relevant_bullets_for_job(candidate_id, job_id, limit=6)
        
        # Build summary
        summary = self._build_summary(job, enhanced_result, top_bullets)
        
        return MatchResult(
            job_id=job_id,
            job_title=job.title,
            company_name=job.company_name,
            match_score=enhanced_result["match_score"],
            total_requirements=enhanced_result["total_reqs"],
            matched_requirements=enhanced_result["matched_reqs"],
            requirement_details=enhanced_result["requirement_details"],
            skill_gaps=enhanced_result["skill_gaps"],
            transferable_skills=enhanced_result["transferable_skills"],
            top_bullets=top_bullets,
            summary=summary
        )
    
    def _calculate_enhanced_match(
        self, 
        candidate_id: str, 
        job_id: str, 
        base_match: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance base match with transferability scoring."""
        
        job = self.engine.get_node(job_id)
        requirements = self.engine.find_job_requirements(job_id)
        
        # Get candidate assets
        candidate_skills = set()
        candidate_tools = set()
        
        roles = self.engine.get_candidate_roles(candidate_id)
        for role in roles:
            bullets = self.engine.get_role_achievements(role.id)
            for bullet in bullets:
                for skill in self.engine.get_bullet_skills(bullet.id):
                    candidate_skills.add(skill.name.lower())
                for tool in self.engine.get_bullet_tools(bullet.id):
                    candidate_tools.add(tool.name.lower())
        
        all_candidate_assets = candidate_skills | candidate_tools
        
        requirement_details = []
        skill_gaps = []
        transferable_skills = {}
        matched_count = 0
        total_weight = 0
        matched_weight = 0
        
        for req in requirements:
            total_weight += req.importance_weight
            
            # Get required skills/tools for this requirement
            req_skills = {s.name.lower() for s in self.engine.get_requirement_skills(req.id)}
            req_tools = {t.name.lower() for t in self.engine.get_requirement_tools(req.id)}
            req_assets = req_skills | req_tools
            
            # Direct matches
            direct_matches = req_assets & all_candidate_assets
            
            # Transferability matches (near matches)
            transfer_matches = {}
            for req_asset in req_assets - direct_matches:
                paths = self.transfer_engine.find_all_transfer_paths(req_asset, list(all_candidate_assets), max_depth=2)
                if paths:
                    best = paths[0]
                    transfer_matches[req_asset] = {
                        "candidate_skill": best.source_skill,
                        "distance": best.distance,
                        "confidence": best.confidence,
                        "transfer_score": best.confidence * (1.0 - best.distance * 0.2)
                    }
            
            # Calculate requirement coverage
            direct_score = len(direct_matches)
            transfer_score = sum(m["transfer_score"] for m in transfer_matches.values())
            req_coverage = min(1.0, direct_score + transfer_score)
            
            if req_coverage > 0:
                matched_weight += req.importance_weight * req_coverage
                matched_count += 1
            
            # Build detail
            matched_skills = [s for s in req_skills if s in all_candidate_assets]
            matched_tools = [t for t in req_tools if t in all_candidate_assets]
            missing_skills = [s for s in req_skills if s not in all_candidate_assets]
            missing_tools = [t for t in req_tools if t not in all_candidate_assets]
            
            # Add transferable skills info
            for asset, tm in transfer_matches.items():
                if asset not in transferable_skills:
                    transferable_skills[asset] = []
                transferable_skills[asset].append({
                    "candidate_skill": tm["candidate_skill"],
                    "score": round(tm["transfer_score"], 3),
                    "distance": tm["distance"]
                })
            
            requirement_details.append({
                "requirement": req.description,
                "importance_weight": req.importance_weight,
                "requirement_type": req.requirement_type,
                "coverage": round(req_coverage, 2),
                "matched_skills": list(matched_skills),
                "matched_tools": list(matched_tools),
                "missing_skills": list(missing_skills),
                "missing_tools": list(missing_tools),
                "transferable_from": {k: [{"skill": v[0]["candidate_skill"], "score": v[0]["score"]} for v in transfer_matches.items()]}
            })
            
            # Build gaps
            for skill in missing_skills:
                skill_gaps.append({
                    "skill": skill,
                    "requirement": req.description,
                    "importance": req.importance_weight,
                    "transferable_from": transfer_matches.get(skill, {}).get("candidate_skill"),
                    "transfer_score": transfer_matches.get(skill, {}).get("transfer_score", 0)
                })
            for tool in missing_tools:
                skill_gaps.append({
                    "tool": tool,
                    "requirement": req.description,
                    "importance": req.importance_weight,
                    "transferable_from": transfer_matches.get(tool, {}).get("candidate_skill"),
                    "transfer_score": transfer_matches.get(tool, {}).get("transfer_score", 0)
                })
        
        # Weighted match score
        match_score = round((matched_weight / total_weight * 100) if total_weight > 0 else 0, 1)
        
        # Sort gaps by importance
        skill_gaps.sort(key=lambda g: -g.get("importance", 0))
        
        return {
            "match_score": match_score,
            "total_reqs": len(requirements),
            "matched_reqs": matched_count,
            "requirement_details": requirement_details,
            "skill_gaps": skill_gaps,
            "transferable_skills": transferable_skills
        }
    
    def _build_summary(self, job, enhanced_result, top_bullets) -> str:
        """Build human-readable match summary."""
        score = enhanced_result["match_score"]
        matched = enhanced_result["matched_reqs"]
        total = enhanced_result["total_reqs"]
        
        if score >= 85:
            level = "EXCELENTE"
        elif score >= 70:
            level = "BOM"
        elif score >= 50:
            level = "MODERADO"
        else:
            level = "BAIXO"
        
        top_skills = []
        for req in enhanced_result["requirement_details"][:3]:
            top_skills.extend(req["matched_skills"][:2])
            top_skills.extend(req["matched_tools"][:1])
        
        summary = f"""
=== ANÁLISE DE MATCH: {job.title} @ {job.company_name} ===

📊 **Score Geral: {score:.1f}% ({level})**
   Requisitos atendidos: {matched}/{total}

✅ **Principais Matches:**
{chr(10).join(f"   • {s}" for s in list(dict.fromkeys(top_skills))[:8])}

⚠️ **Gaps Críticos:**
{chr(10).join(f"   • {g.get('skill') or g.get('tool')} (peso: {g['importance']:.1f})" for g in enhanced_result['skill_gaps'][:5])}

🎯 **Bullets Recomendados para Currículo:**
{chr(10).join(f"   {i}. {b['role']} @ {b['company']}: {b['bullet'][:80]}..." for i, b in enumerate(top_bullets[:4], 1))}
"""
        return summary.strip()


def run_full_analysis(graph_path: str, job_text: str, api_key: str = None) -> Dict[str, Any]:
    """
    Convenience function: Job text → Full analysis (parse + graph + match).
    """
    from engine.job_parser import JobProcessingPipeline
    
    # Load graph
    engine = GraphEngine()
    engine.load_json(graph_path)
    
    # Process job
    pipeline = JobProcessingPipeline(engine, api_key)
    result = pipeline.process_job_text(job_text)
    
    job_id = result["graph_result"]["job_id"]
    
    # Run match analysis
    match_engine = MatchEngine(engine)
    match_result = match_engine.calculate_match(job_id)
    
    # Get GraphRAG context
    retriever = GraphRAGRetriever(engine)
    subgraph = retriever.retrieve_for_job(job_id)
    llm_context = retriever.build_llm_context(subgraph)
    
    return {
        "parsed_job": result["parsed_job"],
        "match_result": match_result,
        "subgraph_context": subgraph,
        "llm_context": llm_context
    }


if __name__ == "__main__":
    print("GraphRAG Retriever & Match Engine ready.")
    print("Usage: run_full_analysis(graph_path, job_text, api_key)")