"""
Career OS — Migration Script: master_resume.json → Knowledge Graph
Converts the flat JSON resume into a rich Knowledge Graph with nodes and edges.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict

from engine.schemas_graph import (
    NodeType, EdgeType, SkillCategory, SeniorityLevel,
    CandidateNode, CompanyNode, RoleNode, ProjectNode, BulletPointNode,
    SkillNode, ToolNode, MetricNode, CareerDNANode,
    create_node, create_edge,
)
from engine.graph_engine import GraphEngine


# ============================
# HELPER FUNCTIONS
# ============================

def clean_text(text: str) -> str:
    """Clean and normalize text."""
    return re.sub(r'\s+', ' ', text.strip())


def extract_metrics(text: str) -> List[Dict[str, str]]:
    """Extract quantifiable metrics from text."""
    metrics = []
    # Patterns for metrics
    patterns = [
        r'([+\-]?\d+(?:[.,]\d+)?%)',  # percentages
        r'(\d+(?:[.,]\d+)?\s*(?:leads|vendas|usuários|seguidores|projetos|contratos|casas|pessoas|participantes))',  # counts
        r'(R\$\s*\d+(?:[.,]\d+)?(?:\s*[km]?)?)',  # currency BRL
        r'(\$\s*\d+(?:[.,]\d+)?(?:\s*[km]?)?)',  # currency USD
        r'(\d+(?:[.,]\d+)?\s*(?:meses?|anos?|semanas?))',  # time periods
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            metrics.append({"value": m, "context": text[:100]})
    return metrics


def parse_skills_from_text(text: str, known_skills: Set[str]) -> List[str]:
    """Extract known skills from text."""
    found = []
    text_lower = text.lower()
    for skill in known_skills:
        if skill.lower() in text_lower:
            found.append(skill)
    return found


def parse_tools_from_text(text: str, known_tools: Set[str]) -> List[str]:
    """Extract known tools from text."""
    found = []
    text_lower = text.lower()
    for tool in known_tools:
        if tool.lower() in text_lower:
            found.append(tool)
    return found


# ============================
# KNOWLEDGE BASES
# ============================

# Known skills from technical_skills section
KNOWN_SKILLS = {
    "Sales Enablement", "Go-to-Market", "GTM", "Sales Productivity", "Playbooks",
    "Stakeholder Management", "Design Thinking", "Lean Startup", "MVP Prototyping",
    "ICP Mapping", "User Journey", "UX/UI", "SEO", "Inbound Marketing",
    "Monetization", "Subscription Models", "CRM", "Sendpulse", "Bitrix24",
    "Salesforce", "n8n", "Make", "Botpress", "API Integrations", "Webhooks",
    "Power BI", "Tableau", "Advanced Excel", "Root Cause Analysis", "OCIR Framework",
    "Meta Quality Methodology", "Funnel Bottleneck Mapping", "Supabase",
    "Agile", "Kanban", "Scrum", "PMO", "Thinking Environment", "Art of Hosting",
    "Bootcamp Training", "Gantt Charts", "Prompt Engineering", "Native AI",
    "WordPress", "Elementor", "LMS", "Figma", "Adobe Creative Suite",
    "Sales Excellence", "Call Listening", "Structured Feedback",
    "Marketing Automation", "Email Marketing", "High-Ticket Sales",
    "Content Marketing", "Technical Narratives", "Facilitation",
    "Business Intelligence", "Data Analysis", "Project Management",
    "Web Scraping", "RAG", "Zero Hallucination", "Conversational AI",
    "WhatsApp Business", "ManyChat", "VPS", "Digital Badges", "Gamification",
    "Ramp-up Reduction", "Quality Assurance", "Cross-Functional Collaboration",
    "Business Continuity Plan", "Data Governance", "LGPD Compliance",
    "E-commerce", "Organic Growth", "Real Estate Lead Gen", "Chatbots",
    "Budget Control", "Timeline Management", "Community Management",
    "Social Innovation", "Collective Intelligence", "Dialogue Circles",
    "Partnership Development", "Conscious Monetization", "Pay What You Want",
    "Financial Operations", "Logistics Coordination", "Recruitment",
    "Clinical Philosophy", "Emotional Intelligence", "Self-Awareness",
    "Corporate Facilitation", "BJJ", "Yoga", "Mindfulness", "HealthTech",
    "Integrative Health", "Longevity", "Global Shapers", "Volunteer Leadership",
    "Crowdfunding", "Emergency Housing", "Education Advocacy", "Mentorship"
}

KNOWN_TOOLS = {
    "n8n", "Make", "Botpress", "ManyChat", "Supabase", "Power BI", "Tableau",
    "Excel", "Bitrix24", "Sendpulse", "Salesforce", "Meta CRM", "WordPress",
    "Elementor", "MasterStudy LMS", "Figma", "Adobe Creative Suite",
    "Google Ads", "Meta Ads", "Meta Business Suite", "VPS", "Web Scraping",
    "Python", "API", "Webhooks", "RAG", "Claude", "ChatGPT", "GitHub",
    "Trello", "Jira", "Notion", "Slack", "Zoom", "Teams", "Miro"
}

SKILL_CATEGORY_MAP = {
    "Sales Enablement": SkillCategory.SALES_OPS,
    "Go-to-Market": SkillCategory.GROWTH,
    "GTM": SkillCategory.GROWTH,
    "Sales Productivity": SkillCategory.SALES_OPS,
    "Playbooks": SkillCategory.SALES_OPS,
    "Stakeholder Management": SkillCategory.LEADERSHIP,
    "Design Thinking": SkillCategory.PRODUCT_DISCOVERY,
    "Lean Startup": SkillCategory.PRODUCT_DISCOVERY,
    "MVP Prototyping": SkillCategory.PRODUCT_DISCOVERY,
    "ICP Mapping": SkillCategory.PRODUCT_DISCOVERY,
    "User Journey": SkillCategory.PRODUCT_DISCOVERY,
    "UX/UI": SkillCategory.PRODUCT_DISCOVERY,
    "SEO": SkillCategory.GROWTH,
    "Inbound Marketing": SkillCategory.GROWTH,
    "Monetization": SkillCategory.GROWTH,
    "Subscription Models": SkillCategory.GROWTH,
    "CRM": SkillCategory.AUTOMATION,
    "Sendpulse": SkillCategory.AUTOMATION,
    "Bitrix24": SkillCategory.AUTOMATION,
    "Salesforce": SkillCategory.AUTOMATION,
    "n8n": SkillCategory.AUTOMATION,
    "Make": SkillCategory.AUTOMATION,
    "Botpress": SkillCategory.AUTOMATION,
    "API Integrations": SkillCategory.TECHNICAL,
    "Webhooks": SkillCategory.TECHNICAL,
    "Power BI": SkillCategory.DATA_ANALYTICS,
    "Tableau": SkillCategory.DATA_ANALYTICS,
    "Advanced Excel": SkillCategory.DATA_ANALYTICS,
    "Root Cause Analysis": SkillCategory.DATA_ANALYTICS,
    "OCIR Framework": SkillCategory.PRODUCT_OPS,
    "Meta Quality Methodology": SkillCategory.PRODUCT_OPS,
    "Funnel Bottleneck Mapping": SkillCategory.DATA_ANALYTICS,
    "Supabase": SkillCategory.TECHNICAL,
    "Agile": SkillCategory.PRODUCT_OPS,
    "Kanban": SkillCategory.PRODUCT_OPS,
    "Scrum": SkillCategory.PRODUCT_OPS,
    "PMO": SkillCategory.PRODUCT_OPS,
    "Thinking Environment": SkillCategory.LEADERSHIP,
    "Art of Hosting": SkillCategory.LEADERSHIP,
    "Bootcamp Training": SkillCategory.LEADERSHIP,
    "Gantt Charts": SkillCategory.PRODUCT_OPS,
    "Prompt Engineering": SkillCategory.AI_ML,
    "Native AI": SkillCategory.AI_ML,
    "WordPress": SkillCategory.TECHNICAL,
    "Elementor": SkillCategory.TECHNICAL,
    "LMS": SkillCategory.TECHNICAL,
    "Figma": SkillCategory.TECHNICAL,
    "Adobe Creative Suite": SkillCategory.TECHNICAL,
    "Sales Excellence": SkillCategory.SALES_OPS,
    "Call Listening": SkillCategory.SALES_OPS,
    "Structured Feedback": SkillCategory.SALES_OPS,
    "Marketing Automation": SkillCategory.GROWTH,
    "Email Marketing": SkillCategory.GROWTH,
    "High-Ticket Sales": SkillCategory.SALES_OPS,
    "Content Marketing": SkillCategory.GROWTH,
    "Technical Narratives": SkillCategory.PMM,
    "Facilitation": SkillCategory.LEADERSHIP,
    "Business Intelligence": SkillCategory.DATA_ANALYTICS,
    "Data Analysis": SkillCategory.DATA_ANALYTICS,
    "Project Management": SkillCategory.PRODUCT_OPS,
    "Web Scraping": SkillCategory.TECHNICAL,
    "RAG": SkillCategory.AI_ML,
    "Zero Hallucination": SkillCategory.AI_ML,
    "Conversational AI": SkillCategory.AI_ML,
    "WhatsApp Business": SkillCategory.TECHNICAL,
    "ManyChat": SkillCategory.AUTOMATION,
    "VPS": SkillCategory.TECHNICAL,
    "Digital Badges": SkillCategory.PRODUCT_OPS,
    "Gamification": SkillCategory.PRODUCT_OPS,
    "Ramp-up Reduction": SkillCategory.LEADERSHIP,
    "Quality Assurance": SkillCategory.PRODUCT_OPS,
    "Cross-Functional Collaboration": SkillCategory.LEADERSHIP,
    "Business Continuity Plan": SkillCategory.PRODUCT_OPS,
    "Data Governance": SkillCategory.PRODUCT_OPS,
    "LGPD Compliance": SkillCategory.PRODUCT_OPS,
    "E-commerce": SkillCategory.GROWTH,
    "Organic Growth": SkillCategory.GROWTH,
    "Real Estate Lead Gen": SkillCategory.GROWTH,
    "Chatbots": SkillCategory.AUTOMATION,
    "Budget Control": SkillCategory.PRODUCT_OPS,
    "Timeline Management": SkillCategory.PRODUCT_OPS,
    "Community Management": SkillCategory.PMM,
    "Social Innovation": SkillCategory.STRATEGY,
    "Collective Intelligence": SkillCategory.LEADERSHIP,
    "Dialogue Circles": SkillCategory.LEADERSHIP,
    "Partnership Development": SkillCategory.GROWTH,
    "Conscious Monetization": SkillCategory.GROWTH,
    "Pay What You Want": SkillCategory.GROWTH,
    "Financial Operations": SkillCategory.PRODUCT_OPS,
    "Logistics Coordination": SkillCategory.PRODUCT_OPS,
    "Recruitment": SkillCategory.LEADERSHIP,
    "Clinical Philosophy": SkillCategory.LEADERSHIP,
    "Emotional Intelligence": SkillCategory.LEADERSHIP,
    "Self-Awareness": SkillCategory.LEADERSHIP,
    "Corporate Facilitation": SkillCategory.LEADERSHIP,
    "BJJ": SkillCategory.LEADERSHIP,
    "Yoga": SkillCategory.LEADERSHIP,
    "Mindfulness": SkillCategory.LEADERSHIP,
    "HealthTech": SkillCategory.STRATEGY,
    "Integrative Health": SkillCategory.STRATEGY,
    "Longevity": SkillCategory.STRATEGY,
    "Global Shapers": SkillCategory.LEADERSHIP,
    "Volunteer Leadership": SkillCategory.LEADERSHIP,
    "Crowdfunding": SkillCategory.GROWTH,
    "Emergency Housing": SkillCategory.STRATEGY,
    "Education Advocacy": SkillCategory.LEADERSHIP,
    "Mentorship": SkillCategory.LEADERSHIP,
}

TOOL_TYPE_MAP = {
    "n8n": "Orchestrator",
    "Make": "Orchestrator",
    "Botpress": "AI/Chatbot",
    "ManyChat": "Chatbot/Automation",
    "Supabase": "Database/Backend",
    "Power BI": "Analytics/BI",
    "Tableau": "Analytics/BI",
    "Excel": "Analytics/Spreadsheet",
    "Bitrix24": "CRM/Automation",
    "Sendpulse": "Email/Automation",
    "Salesforce": "CRM",
    "Meta CRM": "CRM",
    "WordPress": "CMS",
    "Elementor": "Page Builder",
    "MasterStudy LMS": "LMS",
    "Figma": "Design",
    "Adobe Creative Suite": "Design",
    "Google Ads": "Ads Platform",
    "Meta Ads": "Ads Platform",
    "Meta Business Suite": "Social Media Management",
    "VPS": "Infrastructure",
    "Web Scraping": "Data Extraction",
    "Python": "Programming Language",
    "API": "Integration",
    "Webhooks": "Integration",
    "RAG": "AI/Retrieval",
    "Claude": "AI Model",
    "ChatGPT": "AI Model",
    "GitHub": "Version Control",
    "Trello": "Project Management",
    "Jira": "Project Management",
    "Notion": "Knowledge Management",
    "Slack": "Communication",
    "Zoom": "Video Conferencing",
    "Teams": "Communication",
    "Miro": "Visual Collaboration",
}


# ============================
# MIGRATION CLASS
# ============================

class ResumeToGraphMigrator:
    """Migrates master_resume.json to Knowledge Graph."""

    def __init__(self, user_id: str = "kevin_augusto", profile_id: str = "default"):
        self.engine = GraphEngine(user_id=user_id, profile_id=profile_id)
        self.skill_nodes: Dict[str, SkillNode] = {}
        self.tool_nodes: Dict[str, ToolNode] = {}
        self.metric_nodes: Dict[str, MetricNode] = {}
        self.company_nodes: Dict[str, CompanyNode] = {}
        self.role_nodes: Dict[str, RoleNode] = {}
        self.bullet_nodes: Dict[str, BulletPointNode] = {}
        self.project_nodes: Dict[str, ProjectNode] = {}

    def migrate(self, resume_path: str) -> GraphEngine:
        """Run full migration."""
        with open(resume_path, "r", encoding="utf-8") as f:
            resume = json.load(f)

        print("[START] Starting migration: master_resume.json -> Knowledge Graph")

        # 1. Create Candidate
        self._create_candidate(resume["personal_info"])

        # 2. Create Career DNA
        self._create_career_dna(resume)

        # 3. Process Work Experience (Companies, Roles, Bullets)
        self._process_work_experience(resume["work_experience"])

        # 4. Process Technical Skills (create Skill/Tool nodes)
        self._process_technical_skills(resume["technical_skills"])

        # 5. Process Education
        self._process_education(resume["education"])

        # 6. Process Certifications
        self._process_certifications(resume["certifications"])

        # 7. Process Languages
        self._process_languages(resume["languages"])

        # 8. Process Additional Information
        self._process_additional_info(resume["additional_information"])

        # 9. Process Volunteer Experience
        self._process_volunteer(resume["volunteer_experience"])

        # 10. Link bullets to skills/tools/metrics (from text analysis)
        self._link_bullets_to_assets()

        # 11. Build Skill Ontology (SUBSET_OF edges)
        self._build_skill_ontology()

        print("[DONE] Migration complete!")
        self.engine.print_stats()
        return self.engine

    def _create_candidate(self, personal_info: Dict):
        """Create Candidate node."""
        candidate = CandidateNode(
            name=personal_info["name"],
            email=personal_info["email"],
            phone=personal_info["phone"],
            linkedin=personal_info["linkedin"],
            github=personal_info.get("github", ""),
            website=personal_info.get("website", ""),
            location=personal_info["location"].get("pt", ""),
            salary_expectation=personal_info["salary_expectation"].get("pt", ""),
            headline="Product Manager & GTM Specialist | AI & Automation | 8+ years",
            years_experience=8
        )
        self.engine.add_node(candidate)
        self.candidate_id = candidate.id
        print(f"  [USER] Created Candidate: {candidate.name}")

    def _create_career_dna(self, resume: Dict):
        """Create CareerDNA node from additional_info and summaries."""
        additional = resume.get("additional_information", {}).get("pt", [])
        summaries = resume.get("professional_summaries", [])

        values = [
            "Autonomy & Ownership", "Ethical AI", "Human-Centered Design",
            "Continuous Learning", "Impact over Output", "Facilitation over Authority"
        ]

        decision_style = "Data-informed, hypothesis-driven, ethical guardrails"
        leadership_style = "Servant leadership via Thinking Environment facilitation"
        favorite_problems = [
            "Zero-to-one product validation",
            "AI adoption in sales/marketing workflows",
            "Ramp-up acceleration for high-performing teams",
            "Conversion funnel optimization with technical bottlenecks"
        ]

        work_philosophy = " ".join(additional) if additional else ""
        if summaries:
            work_philosophy = summaries[0]["content"].get("pt", "") + " " + work_philosophy

        career_dna = CareerDNANode(
            values=values,
            decision_style=decision_style,
            leadership_style=leadership_style,
            favorite_problems=favorite_problems,
            work_philosophy_pt=work_philosophy,
            work_philosophy_en=" ".join(resume.get("additional_information", {}).get("en", []))
        )
        self.engine.add_node(career_dna)
        self.engine.add_edge(create_edge(EdgeType.HAS_ACHIEVEMENT, self.candidate_id, career_dna.id))
        print(f"  [DNA] Created CareerDNA")

    def _process_work_experience(self, work_experience: List[Dict]):
        """Process all work experience entries."""
        for exp in work_experience:
            company_name = exp["company"]
            location = exp.get("location", {}).get("pt", "")

            # Create/Get Company
            if company_name not in self.company_nodes:
                company = CompanyNode(
                    name=company_name,
                    location=location,
                    industry=self._infer_industry(company_name)
                )
                self.engine.add_node(company)
                self.company_nodes[company_name] = company
                print(f"  [COMPANY] Created Company: {company_name}")

            company = self.company_nodes[company_name]

            # Process Roles
            for role_data in exp.get("roles", []):
                title_pt = role_data["title"].get("pt", "")
                title_en = role_data["title"].get("en", "")
                dates_pt = role_data["dates"].get("pt", "")
                dates_en = role_data["dates"].get("en", "")

                role = RoleNode(
                    title_pt=title_pt,
                    title_en=title_en,
                    start_date=dates_pt,
                    end_date=dates_pt,
                    seniority=self._infer_seniority(title_pt),
                    is_current="Present" in dates_pt or "Atual" in dates_pt
                )
                self.engine.add_node(role)
                self.role_nodes[f"{company_name}:{title_pt}"] = role

                # Connect Candidate -> Role -> Company
                self.engine.add_edge(create_edge(EdgeType.WORKED_AS, self.candidate_id, role.id))
                self.engine.add_edge(create_edge(EdgeType.AT_COMPANY, role.id, company.id))

            # Process Bullets
            bullets = exp.get("bullets", [])
            for i, bullet_data in enumerate(bullets):
                text_pt = bullet_data.get("pt", "")
                text_en = bullet_data.get("en", "")
                tags = bullet_data.get("tags", [])

                # Extract metrics from text
                metrics = extract_metrics(text_pt + " " + text_en)
                metric_str = "; ".join([m["value"] for m in metrics])
                impact_val = self._parse_impact_value(metrics)

                bullet = BulletPointNode(
                    text_pt=text_pt,
                    text_en=text_en,
                    quantifiable_metric=metric_str,
                    impact_value=impact_val,
                    context_pt=f"Role at {company_name}",
                    context_en=f"Role at {company_name}",
                    trade_offs_pt="",
                    trade_offs_en="",
                    star_situation_pt="",
                    star_situation_en="",
                    star_task_pt="",
                    star_task_en="",
                    star_action_pt="",
                    star_action_en="",
                    star_result_pt="",
                    star_result_en=""
                )
                self.engine.add_node(bullet)
                bullet_key = f"{company_name}:bullet_{i}"
                self.bullet_nodes[bullet_key] = bullet

                # Find the most recent role for this company to connect
                role_key = None
                for rk, rv in self.role_nodes.items():
                    if rk.startswith(company_name + ":"):
                        role_key = rk
                        break

                if role_key:
                    role = self.role_nodes[role_key]
                    self.engine.add_edge(create_edge(EdgeType.HAS_ACHIEVEMENT, role.id, bullet.id))

    def _process_technical_skills(self, technical_skills: Dict):
        """Create Skill and Tool nodes from technical_skills."""
        for lang in ["pt", "en"]:
            skills_data = technical_skills.get(lang, [])
            for cat_data in skills_data:
                category = cat_data["category"]
                for skill_name in cat_data["skills"]:
                    skill_name_clean = skill_name.strip()
                    if skill_name_clean in self.skill_nodes:
                        continue

                    cat_enum = SKILL_CATEGORY_MAP.get(skill_name_clean, SkillCategory.TECHNICAL)

                    skill = SkillNode(
                        name=skill_name_clean,
                        category=cat_enum,
                        level=4,  # Default senior level
                        description_pt=skill_name_clean,
                        description_en=skill_name_clean,
                        years_experience=3.0
                    )
                    self.engine.add_node(skill)
                    self.skill_nodes[skill_name_clean] = skill

    def _process_education(self, education: List[Dict]):
        """Create education nodes (as Project nodes for now)."""
        for edu in education:
            project = ProjectNode(
                name=edu["institution"],
                description_pt=edu["degree"].get("pt", ""),
                description_en=edu["degree"].get("en", ""),
                objective_pt="",
                objective_en="",
                start_date=edu["dates"].split("–")[0].strip() if "–" in edu["dates"] else edu["dates"],
                end_date=edu["dates"].split("–")[1].strip() if "–" in edu["dates"] else "",
                status="completed"
            )
            self.engine.add_node(project)
            self.engine.add_edge(create_edge(EdgeType.HAS_ACHIEVEMENT, self.candidate_id, project.id))

    def _process_certifications(self, certifications: List[Dict]):
        """Create certification nodes (as Skill nodes with special category)."""
        for cert in certifications:
            name = cert["name"]
            issuer = cert["issuer"]
            status = cert["status"].get("pt", "")

            skill = SkillNode(
                name=f"{name} ({issuer})",
                category=SkillCategory.TECHNICAL,
                level=4,
                description_pt=f"Certification: {name} by {issuer}. Status: {status}",
                description_en=f"Certification: {name} by {issuer}. Status: {cert['status'].get('en', '')}",
                years_experience=0.5
            )
            self.engine.add_node(skill)
            self.engine.add_edge(create_edge(EdgeType.HAS_ACHIEVEMENT, self.candidate_id, skill.id))

    def _process_languages(self, languages: Dict):
        """Create language skill nodes."""
        for lang in ["pt", "en"]:
            lang_data = languages.get(lang, [])
            for lang_item in lang_data:
                skill = SkillNode(
                    name=f"{lang_item['language']} ({lang_item['proficiency']})",
                    category=SkillCategory.TECHNICAL,
                    level=4 if "avançado" in lang_item["proficiency"].lower() or "advanced" in lang_item["proficiency"].lower() else 2,
                    description_pt=f"Language: {lang_item['language']} - {lang_item['proficiency']}",
                    description_en=f"Language: {lang_item['language']} - {lang_item['proficiency']}",
                    years_experience=5.0
                )
                self.engine.add_node(skill)

    def _process_additional_info(self, additional_info: Dict):
        """Process additional information as Project/Case nodes."""
        for lang in ["pt", "en"]:
            items = additional_info.get(lang, [])
            for item in items:
                project = ProjectNode(
                    name=item[:50] + "..." if len(item) > 50 else item,
                    description_pt=item if lang == "pt" else "",
                    description_en=item if lang == "en" else "",
                    objective_pt="",
                    objective_en="",
                    status="ongoing"
                )
                self.engine.add_node(project)
                self.engine.add_edge(create_edge(EdgeType.HAS_ACHIEVEMENT, self.candidate_id, project.id))

    def _process_volunteer(self, volunteer_experience: List[Dict]):
        """Process volunteer experience."""
        for vol in volunteer_experience:
            org = vol["organization"]
            role_title = vol["role"].get("pt", "")
            dates = vol["dates"]
            desc = vol["description"].get("pt", "")

            company = CompanyNode(
                name=org,
                industry="Non-profit / Volunteering",
                location=vol.get("location", ""),
                description=desc
            )
            self.engine.add_node(company)
            self.company_nodes[org] = company

            role = RoleNode(
                title_pt=role_title,
                title_en=vol["role"].get("en", ""),
                start_date=dates.split("–")[0].strip() if "–" in dates else dates,
                end_date=dates.split("–")[1].strip() if "–" in dates else "",
                seniority=SeniorityLevel.SENIOR,
                is_current=False
            )
            self.engine.add_node(role)
            self.engine.add_edge(create_edge(EdgeType.WORKED_AS, self.candidate_id, role.id))
            self.engine.add_edge(create_edge(EdgeType.AT_COMPANY, role.id, company.id))

    def _link_bullets_to_assets(self):
        """Link bullet points to skills, tools, and metrics based on text analysis."""
        print("  [LINK] Linking bullets to skills, tools, and metrics...")

        for bullet_key, bullet in self.bullet_nodes.items():
            text = bullet.text_pt + " " + bullet.text_en
            text_lower = text.lower()

            # Link Skills
            for skill_name, skill_node in self.skill_nodes.items():
                if skill_name.lower() in text_lower:
                    self.engine.add_edge(create_edge(
                        EdgeType.DEMONSTRATES, bullet.id, skill_node.id,
                        properties={"confidence": 0.9}
                    ))

            # Link Tools
            for tool_name in KNOWN_TOOLS:
                if tool_name.lower() in text_lower:
                    # Create tool node if not exists
                    if tool_name not in self.tool_nodes:
                        tool = ToolNode(
                            name=tool_name,
                            vendor="",
                            tool_type=TOOL_TYPE_MAP.get(tool_name, "Other"),
                            proficiency=4,
                            description_pt=tool_name,
                            description_en=tool_name
                        )
                        self.engine.add_node(tool)
                        self.tool_nodes[tool_name] = tool

                    tool_node = self.tool_nodes[tool_name]
                    self.engine.add_edge(create_edge(
                        EdgeType.UTILIZED, bullet.id, tool_node.id,
                        properties={"proficiency": 4}
                    ))

            # Link Metrics (create metric nodes from extracted metrics)
            metrics = extract_metrics(text)
            for metric in metrics:
                metric_key = metric["value"]
                if metric_key not in self.metric_nodes:
                    metric_node = MetricNode(
                        indicator=metric_key,
                        value_change=metric_key,
                        unit="",
                        baseline="",
                        context_pt=metric["context"],
                        context_en=metric["context"]
                    )
                    self.engine.add_node(metric_node)
                    self.metric_nodes[metric_key] = metric_node

                metric_node = self.metric_nodes[metric_key]
                self.engine.add_edge(create_edge(
                    EdgeType.PRODUCED_IMPACT, bullet.id, metric_node.id
                ))

    def _build_skill_ontology(self):
        """Build SUBSET_OF hierarchy for skills."""
        print("  [ONTOLOGY] Building Skill Ontology (SUBSET_OF)...")

        # Define hierarchy
        hierarchy = {
            # AI & ML
            "Prompt Engineering": "AI & Machine Learning",
            "Native AI": "AI & Machine Learning",
            "RAG": "AI & Machine Learning",
            "Zero Hallucination": "AI & Machine Learning",
            "Conversational AI": "AI & Machine Learning",
            "Claude": "AI & Machine Learning",
            "ChatGPT": "AI & Machine Learning",

            # Automation
            "n8n": "Automation & No-Code",
            "Make": "Automation & No-Code",
            "Botpress": "Automation & No-Code",
            "ManyChat": "Automation & No-Code",
            "Marketing Automation": "Automation & No-Code",
            "Email Marketing": "Automation & No-Code",
            "Chatbots": "Automation & No-Code",
            "CRM": "Automation & No-Code",
            "Sendpulse": "Automation & No-Code",
            "Bitrix24": "Automation & No-Code",
            "Salesforce": "Automation & No-Code",
            "Meta CRM": "Automation & No-Code",
            "API Integrations": "Automation & No-Code",
            "Webhooks": "Automation & No-Code",

            # Product Discovery
            "Design Thinking": "Product Discovery",
            "Lean Startup": "Product Discovery",
            "MVP Prototyping": "Product Discovery",
            "ICP Mapping": "Product Discovery",
            "User Journey": "Product Discovery",
            "UX/UI": "Product Discovery",

            # Growth
            "Go-to-Market": "Growth & Marketing",
            "GTM": "Growth & Marketing",
            "SEO": "Growth & Marketing",
            "Inbound Marketing": "Growth & Marketing",
            "Monetization": "Growth & Marketing",
            "Subscription Models": "Growth & Marketing",
            "Content Marketing": "Growth & Marketing",
            "E-commerce": "Growth & Marketing",
            "Organic Growth": "Growth & Marketing",
            "Real Estate Lead Gen": "Growth & Marketing",
            "Partnership Development": "Growth & Marketing",
            "Conscious Monetization": "Growth & Marketing",
            "Pay What You Want": "Growth & Marketing",
            "Crowdfunding": "Growth & Marketing",
            "Google Ads": "Growth & Marketing",
            "Meta Ads": "Growth & Marketing",
            "Meta Business Suite": "Growth & Marketing",

            # Product Ops
            "Agile": "Product Operations",
            "Kanban": "Product Operations",
            "Scrum": "Product Operations",
            "PMO": "Product Operations",
            "OCIR Framework": "Product Operations",
            "Meta Quality Methodology": "Product Operations",
            "Funnel Bottleneck Mapping": "Product Operations",
            "Digital Badges": "Product Operations",
            "Gamification": "Product Operations",
            "Quality Assurance": "Product Operations",
            "Business Continuity Plan": "Product Operations",
            "Data Governance": "Product Operations",
            "LGPD Compliance": "Product Operations",
            "Budget Control": "Product Operations",
            "Timeline Management": "Product Operations",
            "Gantt Charts": "Product Operations",
            "Project Management": "Product Operations",
            "Financial Operations": "Product Operations",
            "Logistics Coordination": "Product Operations",

            # Sales Ops
            "Sales Enablement": "Sales & Ops",
            "Sales Productivity": "Sales & Ops",
            "Playbooks": "Sales & Ops",
            "Sales Excellence": "Sales & Ops",
            "Call Listening": "Sales & Ops",
            "Structured Feedback": "Sales & Ops",
            "High-Ticket Sales": "Sales & Ops",

            # Data & Analytics
            "Power BI": "Data & Analytics",
            "Tableau": "Data & Analytics",
            "Advanced Excel": "Data & Analytics",
            "Root Cause Analysis": "Data & Analytics",
            "Business Intelligence": "Data & Analytics",
            "Data Analysis": "Data & Analytics",

            # Technical
            "Supabase": "Technical & Engineering",
            "Web Scraping": "Technical & Engineering",
            "WordPress": "Technical & Engineering",
            "Elementor": "Technical & Engineering",
            "LMS": "Technical & Engineering",
            "Figma": "Technical & Engineering",
            "Adobe Creative Suite": "Technical & Engineering",
            "VPS": "Technical & Engineering",
            "Python": "Technical & Engineering",
            "GitHub": "Technical & Engineering",

            # Leadership
            "Stakeholder Management": "Leadership & Management",
            "Thinking Environment": "Leadership & Management",
            "Art of Hosting": "Leadership & Management",
            "Bootcamp Training": "Leadership & Management",
            "Facilitation": "Leadership & Management",
            "Ramp-up Reduction": "Leadership & Management",
            "Cross-Functional Collaboration": "Leadership & Management",
            "Collective Intelligence": "Leadership & Management",
            "Dialogue Circles": "Leadership & Management",
            "Emotional Intelligence": "Leadership & Management",
            "Self-Awareness": "Leadership & Management",
            "Corporate Facilitation": "Leadership & Management",
            "Clinical Philosophy": "Leadership & Management",
            "Global Shapers": "Leadership & Management",
            "Volunteer Leadership": "Leadership & Management",
            "Education Advocacy": "Leadership & Management",
            "Mentorship": "Leadership & Management",
            "Recruitment": "Leadership & Management",
            "BJJ": "Leadership & Management",
            "Yoga": "Leadership & Management",
            "Mindfulness": "Leadership & Management",

            # PMM
            "Technical Narratives": "Product Marketing",
            "Community Management": "Product Marketing",

            # Strategy
            "HealthTech": "Strategy & GTM",
            "Integrative Health": "Strategy & GTM",
            "Longevity": "Strategy & GTM",
            "Emergency Housing": "Strategy & GTM",
            "Social Innovation": "Strategy & GTM",
        }

        # Create category nodes if they don't exist
        category_nodes = {}
        for cat in SkillCategory:
            cat_name = cat.value
            if cat_name not in self.skill_nodes:
                cat_node = SkillNode(
                    name=cat_name,
                    category=cat,
                    level=5,
                    description_pt=f"Category: {cat_name}",
                    description_en=f"Category: {cat_name}",
                    years_experience=10.0
                )
                self.engine.add_node(cat_node)
                self.skill_nodes[cat_name] = cat_node
            category_nodes[cat_name] = self.skill_nodes[cat_name]

        # Create SUBSET_OF edges
        for skill_name, parent_name in hierarchy.items():
            if skill_name in self.skill_nodes and parent_name in self.skill_nodes:
                skill_node = self.skill_nodes[skill_name]
                parent_node = self.skill_nodes[parent_name]
                if skill_node.id != parent_node.id:
                    self.engine.add_edge(create_edge(
                        EdgeType.SUBSET_OF, skill_node.id, parent_node.id
                    ))

        # Add RELATED_TO edges for complementary skills
        related_pairs = [
            ("n8n", "Supabase"),
            ("n8n", "RAG"),
            ("Prompt Engineering", "Claude"),
            ("Prompt Engineering", "ChatGPT"),
            ("Sales Enablement", "CRM"),
            ("Go-to-Market", "SEO"),
            ("Go-to-Market", "Content Marketing"),
            ("Design Thinking", "Lean Startup"),
            ("Thinking Environment", "Facilitation"),
            ("Power BI", "Advanced Excel"),
            ("Root Cause Analysis", "Funnel Bottleneck Mapping"),
            ("Agile", "Scrum"),
            ("Kanban", "Project Management"),
        ]

        for skill_a, skill_b in related_pairs:
            if skill_a in self.skill_nodes and skill_b in self.skill_nodes:
                node_a = self.skill_nodes[skill_a]
                node_b = self.skill_nodes[skill_b]
                self.engine.add_edge(create_edge(
                    EdgeType.RELATED_TO, node_a.id, node_b.id,
                    properties={"strength": 0.7}
                ))

    def _infer_industry(self, company_name: str) -> str:
        """Infer industry from company name."""
        name_lower = company_name.lower()
        if "wipro" in name_lower or "meta" in name_lower:
            return "Technology / Big Tech Consulting"
        elif "barzin" in name_lower:
            return "HealthTech / FoodTech Startup"
        elif "ak branding" in name_lower:
            return "Creative Agency / Branding"
        elif "munzner" in name_lower:
            return "Education / Professional Development"
        elif "conversas" in name_lower:
            return "Social Innovation / Community"
        elif "alvesa" in name_lower:
            return "Logistics / Transportation"
        return "Other"

    def _infer_seniority(self, title: str) -> SeniorityLevel:
        """Infer seniority from title."""
        title_lower = title.lower()
        if any(kw in title_lower for kw in ["director", "vp", "vice president", "head of", "c-level", "chief"]):
            return SeniorityLevel.DIRECTOR
        elif any(kw in title_lower for kw in ["lead", "principal", "manager", "coordenador", "gerente"]):
            return SeniorityLevel.LEAD
        elif any(kw in title_lower for kw in ["senior", "sênior", "especialista", "specialist", "expert"]):
            return SeniorityLevel.SENIOR
        elif any(kw in title_lower for kw in ["founder", "co-founder", "fundador"]):
            return SeniorityLevel.LEAD
        elif any(kw in title_lower for kw in ["junior", "júnior", "estagiário", "intern", "assistant", "assistente"]):
            return SeniorityLevel.JUNIOR
        return SeniorityLevel.MID

    def _parse_impact_value(self, metrics: List[Dict]) -> float:
        """Parse numeric impact value from metrics."""
        for m in metrics:
            val = m["value"]
            # Try to extract number
            nums = re.findall(r'[\d.,]+', val.replace('%', '').replace('R$', '').replace('$', ''))
            if nums:
                try:
                    return float(nums[0].replace(',', '.'))
                except ValueError:
                    pass
        return 0.0


# ============================
# MAIN
# ============================

if __name__ == "__main__":
    import sys

    resume_path = sys.argv[1] if len(sys.argv) > 1 else "master_resume.json"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "data/graph_export.json"

    migrator = ResumeToGraphMigrator()
    engine = migrator.migrate(resume_path)

    # Save graph
    engine.save_json(output_path)
    print(f"\n[SAVE] Graph saved to: {output_path}")