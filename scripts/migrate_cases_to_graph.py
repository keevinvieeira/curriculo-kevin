"""
Career OS — Migration Script: Cases JSON → Knowledge Graph
Loads case files and creates CaseNode + STARStoryNode + links to Skills/Tools/Metrics.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Set, Any

from engine.schemas_graph import (
    NodeType, EdgeType, SkillCategory,
    CaseNode, STARStoryNode, SkillNode, ToolNode, MetricNode,
    create_node, create_edge,
)
from engine.graph_engine import GraphEngine


def load_all_cases(cases_dir: str = "data/cases") -> List[Dict]:
    """Load all case JSON files from directory."""
    cases = []
    case_files = [
        "wipro_cases.json",
        "meubarzin_cases.json",
        "ak_cases.json",
        "munzner_cases.json",
        "conversas_cases.json",
        "volunteer_cases.json",
        "early_career_cases.json"
    ]
    
    for fname in case_files:
        fpath = Path(cases_dir) / fname
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                file_cases = json.load(f)
                cases.extend(file_cases)
                print(f"  Loaded {len(file_cases)} cases from {fname}")
        else:
            print(f"  [WARN] Not found: {fname}")
    
    return cases


def get_or_create_skill(engine: GraphEngine, skill_name: str, skill_nodes: Dict[str, SkillNode]) -> SkillNode:
    """Get existing skill node or create new one."""
    if skill_name in skill_nodes:
        return skill_nodes[skill_name]
    
    # Determine category from known mapping
    category_map = {
        # ... (use the same mapping as migrate_json_to_graph.py)
    }
    
    skill = SkillNode(
        name=skill_name,
        category=SkillCategory.TECHNICAL,  # Default, will be refined
        level=4,
        description_pt=skill_name,
        description_en=skill_name,
        years_experience=3.0
    )
    engine.add_node(skill)
    skill_nodes[skill_name] = skill
    return skill


def get_or_create_tool(engine: GraphEngine, tool_name: str, tool_nodes: Dict[str, ToolNode]) -> ToolNode:
    """Get existing tool node or create new one."""
    if tool_name in tool_nodes:
        return tool_nodes[tool_name]
    
    tool_types = {
        "n8n": "Orchestrator", "Make": "Orchestrator", "Zapier": "Orchestrator",
        "Botpress": "AI/Chatbot", "ManyChat": "Chatbot/Automation",
        "Supabase": "Database/Backend", "PostgreSQL": "Database",
        "Power BI": "Analytics/BI", "Tableau": "Analytics/BI", "Excel": "Analytics/Spreadsheet",
        "Bitrix24": "CRM/Automation", "Sendpulse": "Email/Automation", "Salesforce": "CRM",
        "Meta CRM": "CRM", "HubSpot": "CRM", "Pipedrive": "CRM",
        "WordPress": "CMS", "WooCommerce": "E-Commerce", "Elementor": "Page Builder",
        "MasterStudy LMS": "LMS", "Figma": "Design", "Adobe Creative Suite": "Design",
        "Google Ads": "Ads Platform", "Meta Ads": "Ads Platform", "Meta Business Suite": "Social Media",
        "VPS": "Infrastructure", "Python": "Programming Language",
        "API": "Integration", "Webhooks": "Integration", "RAG": "AI/Retrieval",
        "Claude": "AI Model", "ChatGPT": "AI Model", "GitHub": "Version Control",
        "Trello": "Project Management", "Jira": "Project Management", "Notion": "Knowledge Management",
        "Slack": "Communication", "Zoom": "Video Conferencing", "Teams": "Communication",
        "Miro": "Visual Collaboration", "Hotjar": "Analytics/UX", "Google Analytics": "Analytics",
        "Google Search Console": "SEO", "Ahrefs": "SEO", "SEMrush": "SEO",
        "Catarse": "Crowdfunding", "WhatsApp": "Messaging", "Instagram": "Social Media",
        "LinkedIn": "Professional Network", "Zoom": "Video Conferencing", "Google Forms": "Forms",
        "Google Sheets": "Spreadsheet", "PDF Toolkit": "Document", "Video Editing": "Media"
    }
    
    tool = ToolNode(
        name=tool_name,
        vendor="",
        tool_type=tool_types.get(tool_name, "Other"),
        proficiency=4,
        description_pt=tool_name,
        description_en=tool_name
    )
    engine.add_node(tool)
    tool_nodes[tool_name] = tool
    return tool


def get_or_create_metric(engine: GraphEngine, metric_str: str, metric_nodes: Dict[str, MetricNode]) -> MetricNode:
    """Get existing metric node or create new one."""
    if metric_str in metric_nodes:
        return metric_nodes[metric_str]
    
    metric = MetricNode(
        indicator=metric_str,
        value_change=metric_str,
        unit="",
        baseline="",
        context_pt=metric_str,
        context_en=metric_str
    )
    engine.add_node(metric)
    metric_nodes[metric_str] = metric
    return metric


def migrate_cases_to_graph(
    engine: GraphEngine,
    candidate_id: str,
    cases_dir: str = "data/cases"
) -> GraphEngine:
    """Migrate all cases to the knowledge graph."""
    
    print("[START] Migrating cases to Knowledge Graph...")
    
    # Load all cases
    cases = load_all_cases(cases_dir)
    print(f"  Total cases to migrate: {len(cases)}")
    
    # Track created nodes for linking
    skill_nodes: Dict[str, SkillNode] = {}
    tool_nodes: Dict[str, ToolNode] = {}
    metric_nodes: Dict[str, MetricNode] = {}
    case_nodes: Dict[str, CaseNode] = {}
    star_nodes: Dict[str, STARStoryNode] = {}
    
    # Load existing skills/tools from graph
    for node in engine.get_nodes_by_type(NodeType.SKILL):
        skill_nodes[node.name] = node
    for node in engine.get_nodes_by_type(NodeType.TOOL):
        tool_nodes[node.name] = node
    for node in engine.get_nodes_by_type(NodeType.METRIC):
        metric_nodes[node.value_change] = node
    
    # Find company nodes
    company_nodes: Dict[str, Any] = {}
    for node in engine.get_nodes_by_type(NodeType.COMPANY):
        company_nodes[node.name] = node
    
    # Find role nodes
    role_nodes: Dict[str, Any] = {}
    for node in engine.get_nodes_by_type(NodeType.ROLE):
        key = f"{node.title_pt} @ {engine.get_role_company(node.id).name if engine.get_role_company(node.id) else 'Unknown'}"
        role_nodes[key] = node
    
    for i, case_data in enumerate(cases):
        title_safe = case_data['title'].encode('ascii', 'replace').decode('ascii')
        print(f"  [{i+1}/{len(cases)}] Migrating: {title_safe}")
        
        # Create Case Node
        case_node = CaseNode(
            title=case_data["title"],
            company=case_data["company"],
            context_pt=case_data.get("context_pt", ""),
            context_en=case_data.get("context_en", ""),
            challenge_pt=case_data.get("challenge_pt", ""),
            challenge_en=case_data.get("challenge_en", ""),
            problem_pt=case_data.get("problem_pt", ""),
            problem_en=case_data.get("problem_en", ""),
            hypotheses_pt=case_data.get("hypotheses_pt", ""),
            hypotheses_en=case_data.get("hypotheses_en", ""),
            decisions_pt=case_data.get("decisions_pt", ""),
            decisions_en=case_data.get("decisions_en", ""),
            tradeoffs_pt=case_data.get("tradeoffs_pt", ""),
            tradeoffs_en=case_data.get("tradeoffs_en", ""),
            results_pt=case_data.get("results_pt", ""),
            results_en=case_data.get("results_en", ""),
            metrics=case_data.get("metrics", [])
        )
        engine.add_node(case_node)
        case_nodes[case_data["title"]] = case_node
        
        # Link Case to Company
        company_name = case_data["company"]
        if company_name in company_nodes:
            company = company_nodes[company_name]
            engine.add_edge(create_edge(EdgeType.HAS_CASE, company.id, case_node.id))
        
        # Link Case to Role (find matching role)
        role_title = case_data.get("role", "")
        for role_key, role_node in role_nodes.items():
            if role_title in role_key or role_key in role_title:
                engine.add_edge(create_edge(EdgeType.BELONGS_TO_PROJECT, role_node.id, case_node.id))
                break
        
        # Create STAR Story Node
        star_node = STARStoryNode(
            situation_pt=case_data.get("star_situation_pt", ""),
            situation_en=case_data.get("star_situation_en", ""),
            task_pt=case_data.get("star_task_pt", ""),
            task_en=case_data.get("star_task_en", ""),
            action_pt=case_data.get("star_action_pt", ""),
            action_en=case_data.get("star_action_en", ""),
            result_pt=case_data.get("star_result_pt", ""),
            result_en=case_data.get("star_result_en", ""),
            competency_tags=case_data.get("competency_tags", []),
            difficulty=case_data.get("difficulty", 3)
        )
        engine.add_node(star_node)
        star_nodes[case_data["title"]] = star_node
        
        # Link Case to STAR Story
        engine.add_edge(create_edge(EdgeType.HAS_STAR_STORY, case_node.id, star_node.id))
        
        # Link Skills
        for skill_name in case_data.get("skills", []):
            skill_node = get_or_create_skill(engine, skill_name, skill_nodes)
            engine.add_edge(create_edge(
                EdgeType.DEMONSTRATES, case_node.id, skill_node.id,
                properties={"confidence": 0.9}
            ))
            # Also link STAR story to skills
            engine.add_edge(create_edge(
                EdgeType.DEMONSTRATES, star_node.id, skill_node.id,
                properties={"confidence": 0.9}
            ))
        
        # Link Tools
        for tool_name in case_data.get("tools", []):
            tool_node = get_or_create_tool(engine, tool_name, tool_nodes)
            engine.add_edge(create_edge(
                EdgeType.UTILIZED, case_node.id, tool_node.id,
                properties={"proficiency": 4}
            ))
            engine.add_edge(create_edge(
                EdgeType.UTILIZED, star_node.id, tool_node.id,
                properties={"proficiency": 4}
            ))
        
        # Link Metrics
        for metric_str in case_data.get("metrics", []):
            metric_node = get_or_create_metric(engine, metric_str, metric_nodes)
            engine.add_edge(create_edge(
                EdgeType.PRODUCED_IMPACT, case_node.id, metric_node.id
            ))
            engine.add_edge(create_edge(
                EdgeType.PRODUCED_IMPACT, star_node.id, metric_node.id
            ))
        
        # Link Case to Candidate (for easy traversal)
        engine.add_edge(create_edge(EdgeType.HAS_ACHIEVEMENT, candidate_id, case_node.id))
        engine.add_edge(create_edge(EdgeType.HAS_ACHIEVEMENT, candidate_id, star_node.id))
    
    print(f"[DONE] Cases migration complete!")
    print(f"  Cases created: {len(case_nodes)}")
    print(f"  STAR stories created: {len(star_nodes)}")
    print(f"  New skills added: {len([s for s in skill_nodes.values() if s not in engine.get_nodes_by_type(NodeType.SKILL)])}")
    
    return engine


if __name__ == "__main__":
    import sys
    
    # Load existing graph
    graph_path = sys.argv[1] if len(sys.argv) > 1 else "data/graph_export.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/graph_with_cases.json"
    
    engine = GraphEngine()
    engine.load_json(graph_path)
    print(f"Loaded base graph: {engine.stats()['total_nodes']} nodes, {engine.stats()['total_edges']} edges")
    
    # Find candidate
    candidates = engine.get_nodes_by_type(NodeType.CANDIDATE)
    if not candidates:
        print("[ERROR] No candidate found in graph!")
        sys.exit(1)
    
    candidate_id = candidates[0].id
    print(f"Found candidate: {candidates[0].name} ({candidate_id})")
    
    # Migrate cases
    engine = migrate_cases_to_graph(engine, candidate_id)
    
    # Save updated graph
    engine.save_json(output_path)
    print(f"\n[SAVE] Updated graph saved to: {output_path}")
    engine.print_stats()