"""
Career OS — Seed Ontology Script
Creates the initial Skill Taxonomy (SUBSET_OF hierarchy) as JSON and loads into graph.
"""

import json
from pathlib import Path
from typing import Dict, List, Any

from engine.schemas_graph import (
    NodeType, EdgeType, SkillCategory,
    SkillNode, create_node, create_edge,
)
from engine.graph_engine import GraphEngine


# ============================
# SKILL TAXONOMY DEFINITION
# ============================

SKILL_TAXONOMY = {
    "AI & Machine Learning": {
        "category": "AI & Machine Learning",
        "description": "Artificial Intelligence, Machine Learning, LLMs, Prompt Engineering",
        "skills": {
            "Prompt Engineering": "Professional prompt design for LLMs (Claude, GPT, Gemini)",
            "Native AI Implementation": "Integrating AI models into production workflows",
            "RAG (Retrieval-Augmented Generation)": "Building retrieval-augmented generation systems",
            "Zero Hallucination Rules": "Constraint design for factual AI outputs",
            "Conversational AI": "Chatbot/voice agent design and architecture",
            "LLM Evaluation": "Testing and benchmarking LLM outputs",
            "AI Agents": "Autonomous agent architectures (LangChain, AutoGPT patterns)",
            "Vector Databases": "Pinecone, Weaviate, Chroma for embeddings storage",
            "Embeddings": "Text embedding models and similarity search",
            "Fine-tuning": "Parameter-efficient fine-tuning (LoRA, QLoRA)",
        }
    },
    "Automation & No-Code": {
        "category": "Automation & No-Code",
        "description": "Workflow automation, orchestration, no-code/low-code platforms",
        "skills": {
            "n8n": "Self-hosted workflow automation platform",
            "Make (Integromat)": "Visual automation platform for app integration",
            "Zapier": "Cloud-based automation between web apps",
            "Botpress": "Open-source chatbot platform",
            "ManyChat": "Messenger/Instagram/WhatsApp automation",
            "CRM Automation": "Salesforce, HubSpot, Pipedrive workflow automation",
            "Email Marketing Automation": "Sendpulse, ActiveCampaign, Mailchimp journeys",
            "WhatsApp Business API": "Official WhatsApp integration for business",
            "API/Webhook Integrations": "Custom integration development",
            "Process Mining": "Discovering and optimizing business processes",
        }
    },
    "Product Discovery": {
        "category": "Product Discovery",
        "description": "Product discovery, validation, user research, experimentation",
        "skills": {
            "Design Thinking": "Human-centered problem solving methodology",
            "Lean Startup": "Build-Measure-Learn cycles, MVP validation",
            "MVP Prototyping": "Rapid prototype development and testing",
            "ICP Mapping": "Ideal Customer Profile definition and segmentation",
            "User Journey Mapping": "End-to-end user experience visualization",
            "UX/UI Design": "Figma, user interface and experience design",
            "User Research": "Interviews, surveys, usability testing",
            "Jobs-to-be-Done": "JTBD framework for understanding customer needs",
            "Product Analytics": "Mixpanel, Amplitude, event tracking",
            "A/B Testing": "Experimentation design and statistical analysis",
        }
    },
    "Growth & Marketing": {
        "category": "Growth & Marketing",
        "description": "Growth marketing, acquisition, retention, monetization",
        "skills": {
            "Go-to-Market Strategy": "GTM planning, launch execution, market entry",
            "SEO & Organic Growth": "Technical SEO, content strategy, link building",
            "Inbound Marketing": "Content marketing, lead magnets, nurture funnels",
            "Paid Acquisition": "Google Ads, Meta Ads, LinkedIn Ads management",
            "Conversion Rate Optimization": "CRO, landing page optimization, funnel analysis",
            "Monetization Models": "Subscription, freemium, usage-based pricing",
            "Email Marketing": "Lifecycle campaigns, segmentation, deliverability",
            "Marketing Automation": "Lead scoring, drip campaigns, behavioral triggers",
            "Affiliate/Referral Programs": "Partner marketing, viral loops",
            "Community Building": "Community-led growth, ambassador programs",
        }
    },
    "Product Operations": {
        "category": "Product Operations",
        "description": "Product operations, project management, quality, compliance",
        "skills": {
            "Agile Methodologies": "Scrum, Kanban, SAFe, sprint planning",
            "PMO Guidelines": "Project Management Office standards and governance",
            "Project Scheduling": "Gantt charts, critical path, resource allocation",
            "Quality Assurance": "Testing strategies, audit frameworks, quality gates",
            "OCIR Framework": "Objective, Context, Input, Result framework",
            "Meta Quality Methodology": "Meta's proprietary quality standards",
            "Funnel Bottleneck Mapping": "Identifying and resolving conversion blockers",
            "Business Continuity Planning": "BCP, disaster recovery, risk mitigation",
            "Data Governance": "Data quality, lineage, privacy compliance",
            "LGPD/GDPR Compliance": "Privacy law implementation and auditing",
            "Budget & Timeline Control": "Financial planning, burn rate, runway management",
            "Cross-Functional Coordination": "Stakeholder alignment, dependency management",
        }
    },
    "Sales & Operations": {
        "category": "Sales & Operations",
        "description": "Sales enablement, productivity, operations, methodologies",
        "skills": {
            "Sales Enablement": "Training, content, tools for sales productivity",
            "Sales Excellence": "Methodology implementation (MEDDIC, SPIN, Challenger)",
            "Call Listening & Coaching": "Gong, Chorus, structured feedback loops",
            "Playbooks & Scripts": "Battle cards, objection handling, talk tracks",
            "Sales Productivity": "Ramp-up acceleration, time-to-productivity reduction",
            "CRM Administration": "Salesforce, HubSpot, Meta CRM configuration",
            "Pipeline Management": "Forecasting, deal inspection, pipeline hygiene",
            "Territory Planning": "Quota setting, account segmentation, capacity planning",
            "Partner Enablement": "Channel partner training and certification",
            "Revenue Operations": "RevOps, GTM alignment, data-driven decisions",
        }
    },
    "Data & Analytics": {
        "category": "Data & Analytics",
        "description": "Business intelligence, data analysis, visualization, insights",
        "skills": {
            "Power BI": "DAX, data modeling, dashboard development",
            "Tableau": "Visual analytics, calculated fields, server admin",
            "Advanced Excel": "Pivot tables, Power Query, complex formulas",
            "SQL": "Query optimization, window functions, CTEs",
            "Root Cause Analysis": "5 Whys, Fishbone, Pareto analysis",
            "Statistical Analysis": "Hypothesis testing, regression, significance",
            "Data Visualization": "Chart selection, storytelling, executive dashboards",
            "ETL/ELT Pipelines": "Data ingestion, transformation, orchestration",
            "Supabase/PostgreSQL": "Database design, RLS, real-time subscriptions",
            "Web Scraping": "BeautifulSoup, Selenium, Playwright, ethics",
        }
    },
    "Technical & Engineering": {
        "category": "Technical & Engineering",
        "description": "Software development, infrastructure, DevOps, architecture",
        "skills": {
            "Python": "Scripting, automation, data processing, FastAPI",
            "JavaScript/TypeScript": "Node.js, React, Next.js, frontend development",
            "REST/GraphQL APIs": "API design, OpenAPI, authentication, rate limiting",
            "Database Design": "PostgreSQL, MongoDB, schema modeling, indexing",
            "Docker": "Containerization, multi-stage builds, compose",
            "Kubernetes": "Orchestration, helm charts, scaling, monitoring",
            "CI/CD": "GitHub Actions, GitLab CI, deployment pipelines",
            "Cloud Platforms": "AWS, GCP, Azure - core services",
            "VPS Management": "Linux, Nginx, SSL, systemd, monitoring",
            "Git/GitHub": "Version control, branching strategies, code review",
            "Figma": "Design systems, prototyping, developer handoff",
            "WordPress/Elementor": "CMS development, theme customization, LMS",
        }
    },
    "Leadership & Management": {
        "category": "Leadership & Management",
        "description": "People leadership, facilitation, coaching, organizational design",
        "skills": {
            "Servant Leadership": "Team empowerment, obstacle removal, growth focus",
            "Thinking Environment": "Nancy Kline's 10 components, generative attention",
            "Art of Hosting": "Participatory leadership, World Café, Open Space",
            "Facilitation": "Workshop design, group dynamics, decision-making",
            "Coaching & Mentoring": "GROW model, career development, feedback",
            "Team Building": "Psychological safety, trust, high-performance teams",
            "Change Management": "ADKAR, Kotter, organizational transformation",
            "Stakeholder Management": "Influence without authority, negotiation",
            "Bootcamp Design": "Intensive training programs, gamification, assessment",
            "Ramp-up Acceleration": "Onboarding optimization, time-to-productivity",
            "Performance Management": "OKRs, KPIs, continuous feedback, reviews",
            "Conflict Resolution": "Mediation, difficult conversations, restoration",
        }
    },
    "Product Marketing": {
        "category": "Product Marketing",
        "description": "Positioning, messaging, launch, competitive intelligence",
        "skills": {
            "Positioning & Messaging": "April Dunford framework, value propositions",
            "Product Launch": "Launch tiers, checklists, cross-functional coordination",
            "Competitive Intelligence": "Battle cards, win/loss analysis, positioning",
            "Customer Marketing": "Case studies, references, advocacy programs",
            "Sales Enablement Content": "Decks, one-pagers, demo scripts, ROI calculators",
            "Technical Writing": "Documentation, API docs, developer guides",
            "Analyst Relations": "Gartner, Forrester, briefings, Magic Quadrant",
            "Community Marketing": "Developer relations, user groups, events",
        }
    },
    "Strategy & GTM": {
        "category": "Strategy & GTM",
        "description": "Corporate strategy, market analysis, business model design",
        "skills": {
            "Business Model Canvas": "Value prop, customer segments, revenue streams",
            "Market Sizing": "TAM/SAM/SOM, bottom-up, top-down estimation",
            "Unit Economics": "LTV/CAC, payback period, contribution margin",
            "Pricing Strategy": "Value-based, tiered, usage-based, psychological",
            "Partnership Strategy": "Co-selling, integration partnerships, ecosystems",
            "International Expansion": "Localization, compliance, go-to-market",
            "M&A Integration": "Due diligence, integration planning, synergy capture",
            "Innovation Management": "Horizon 1/2/3, portfolio management, ventures",
        }
    },
}


# ============================
# RELATED_TO EDGES (Semantic adjacency)
# ============================

RELATED_SKILLS = [
    # AI + Automation
    ("Prompt Engineering", "Native AI Implementation", 0.9),
    ("Prompt Engineering", "RAG (Retrieval-Augmented Generation)", 0.8),
    ("RAG (Retrieval-Augmented Generation)", "Vector Databases", 0.9),
    ("RAG (Retrieval-Augmented Generation)", "Embeddings", 0.9),
    ("Conversational AI", "n8n", 0.7),
    ("Conversational AI", "ManyChat", 0.7),
    ("Conversational AI", "WhatsApp Business API", 0.8),
    ("AI Agents", "n8n", 0.7),
    ("LLM Evaluation", "Prompt Engineering", 0.8),

    # Automation + Data
    ("n8n", "Supabase/PostgreSQL", 0.8),
    ("n8n", "API/Webhook Integrations", 0.9),
    ("Make (Integromat)", "CRM Automation", 0.8),
    ("Zapier", "Email Marketing Automation", 0.7),

    # Product Discovery + Growth
    ("Design Thinking", "Lean Startup", 0.9),
    ("MVP Prototyping", "A/B Testing", 0.8),
    ("ICP Mapping", "Go-to-Market Strategy", 0.9),
    ("User Journey Mapping", "Conversion Rate Optimization", 0.8),
    ("Product Analytics", "A/B Testing", 0.9),
    ("SEO & Organic Growth", "Content Marketing", 0.8),

    # Growth + Sales
    ("Go-to-Market Strategy", "Sales Enablement", 0.9),
    ("Paid Acquisition", "Landing Page Optimization", 0.8),
    ("Email Marketing", "Marketing Automation", 0.9),
    ("Lead Scoring", "Sales Productivity", 0.7),

    # Product Ops + Leadership
    ("Agile Methodologies", "Facilitation", 0.7),
    ("Project Scheduling", "Cross-Functional Coordination", 0.8),
    ("Quality Assurance", "Root Cause Analysis", 0.8),
    ("Bootcamp Design", "Coaching & Mentoring", 0.8),
    ("Ramp-up Acceleration", "Onboarding Optimization", 0.9),

    # Data + Technical
    ("Power BI", "SQL", 0.8),
    ("Tableau", "Data Visualization", 0.9),
    ("ETL/ELT Pipelines", "Supabase/PostgreSQL", 0.7),
    ("Python", "Web Scraping", 0.8),
    ("Docker", "Kubernetes", 0.7),
    ("CI/CD", "Cloud Platforms", 0.8),

    # Leadership + Strategy
    ("Servant Leadership", "Thinking Environment", 0.8),
    ("Stakeholder Management", "Negotiation", 0.7),
    ("Change Management", "Business Model Canvas", 0.6),
    ("Team Building", "Psychological Safety", 0.9),

    # PMM + Growth
    ("Positioning & Messaging", "Go-to-Market Strategy", 0.9),
    ("Product Launch", "Competitive Intelligence", 0.8),
    ("Sales Enablement Content", "Playbooks & Scripts", 0.8),
]


# ============================
# MAIN SEEDING FUNCTION
# ============================

def seed_ontology(user_id: str = "kevin_augusto", profile_id: str = "default") -> GraphEngine:
    """Create and populate the skill ontology in the graph."""
    engine = GraphEngine(user_id=user_id, profile_id=profile_id)

    print("[SEED] Seeding Skill Ontology...")

    # Track created skill nodes by name
    skill_nodes: Dict[str, SkillNode] = {}
    category_nodes: Dict[str, SkillNode] = {}

    # 1. Create Category nodes (Level 1)
    for cat_name, cat_data in SKILL_TAXONOMY.items():
        cat_enum = SkillCategory(cat_data["category"])
        cat_node = SkillNode(
            name=cat_name,
            category=cat_enum,
            level=5,
            description_pt=cat_data["description"],
            description_en=cat_data["description"],
            years_experience=10.0
        )
        engine.add_node(cat_node)
        category_nodes[cat_name] = cat_node
        print(f"  [CAT] Category: {cat_name}")

    # 2. Create Skill nodes (Level 2) and link to categories
    for cat_name, cat_data in SKILL_TAXONOMY.items():
        cat_node = category_nodes[cat_name]
        cat_enum = SkillCategory(cat_data["category"])

        for skill_name, skill_desc in cat_data["skills"].items():
            skill_node = SkillNode(
                name=skill_name,
                category=cat_enum,
                level=4,
                description_pt=skill_desc,
                description_en=skill_desc,
                years_experience=3.0
            )
            engine.add_node(skill_node)
            skill_nodes[skill_name] = skill_node

            # SUBSET_OF: skill -> category
            engine.add_edge(create_edge(
                EdgeType.SUBSET_OF, skill_node.id, cat_node.id
            ))

    # 3. Add RELATED_TO edges (semantic adjacency)
    print("  [LINK] Adding RELATED_TO edges...")
    for skill_a, skill_b, strength in RELATED_SKILLS:
        if skill_a in skill_nodes and skill_b in skill_nodes:
            node_a = skill_nodes[skill_a]
            node_b = skill_nodes[skill_b]
            engine.add_edge(create_edge(
                EdgeType.RELATED_TO, node_a.id, node_b.id,
                properties={"strength": strength}
            ))
            # Add bidirectional
            engine.add_edge(create_edge(
                EdgeType.RELATED_TO, node_b.id, node_a.id,
                properties={"strength": strength}
            ))

    # 4. Add cross-category SUBSET_OF for sub-categories
    sub_categories = {
        "LLM Fundamentals": ["Prompt Engineering", "Native AI Implementation", "RAG (Retrieval-Augmented Generation)", "Zero Hallucination Rules"],
        "Chatbot Platforms": ["Conversational AI", "Botpress", "ManyChat", "WhatsApp Business API"],
        "Workflow Automation": ["n8n", "Make (Integromat)", "Zapier", "API/Webhook Integrations"],
        "CRM & Marketing Automation": ["CRM Automation", "Email Marketing Automation", "Marketing Automation"],
        "Product Validation": ["Design Thinking", "Lean Startup", "MVP Prototyping", "A/B Testing"],
        "User Research": ["ICP Mapping", "User Journey Mapping", "User Research", "Jobs-to-be-Done"],
        "Acquisition Channels": ["SEO & Organic Growth", "Paid Acquisition", "Affiliate/Referral Programs"],
        "Retention & Monetization": ["Email Marketing", "Marketing Automation", "Monetization Models", "Community Building"],
        "Agile & Delivery": ["Agile Methodologies", "Project Scheduling", "Cross-Functional Coordination"],
        "Quality & Compliance": ["Quality Assurance", "Business Continuity Planning", "Data Governance", "LGPD/GDPR Compliance"],
        "Sales Methodologies": ["Sales Enablement", "Sales Excellence", "Sales Productivity", "Pipeline Management"],
        "BI & Visualization": ["Power BI", "Tableau", "Data Visualization", "Advanced Excel"],
        "Data Engineering": ["SQL", "ETL/ELT Pipelines", "Supabase/PostgreSQL", "Web Scraping"],
        "DevOps & Cloud": ["Docker", "Kubernetes", "CI/CD", "Cloud Platforms", "VPS Management"],
        "People Leadership": ["Servant Leadership", "Coaching & Mentoring", "Team Building", "Performance Management"],
        "Facilitation Methods": ["Thinking Environment", "Art of Hosting", "Facilitation", "Bootcamp Design"],
    }

    for sub_cat_name, skills in sub_categories.items():
        # Create sub-category node
        sub_cat_node = SkillNode(
            name=sub_cat_name,
            category=SkillCategory.TECHNICAL,  # Will be overridden
            level=4,
            description_pt=f"Sub-category: {sub_cat_name}",
            description_en=f"Sub-category: {sub_cat_name}",
            years_experience=5.0
        )
        engine.add_node(sub_cat_node)

        # Link to parent category (find best match)
        for skill_name in skills:
            if skill_name in skill_nodes:
                skill_node = skill_nodes[skill_name]
                # SUBSET_OF: skill -> sub-category
                engine.add_edge(create_edge(
                    EdgeType.SUBSET_OF, skill_node.id, sub_cat_node.id
                ))

        # Link sub-category to main category
        # Find parent category by checking first skill's category
        for skill_name in skills:
            if skill_name in skill_nodes:
                skill_node = skill_nodes[skill_name]
                parent_cat_name = None
                for cat_name, cat_data in SKILL_TAXONOMY.items():
                    if skill_name in cat_data["skills"]:
                        parent_cat_name = cat_name
                        break
                if parent_cat_name and parent_cat_name in category_nodes:
                    engine.add_edge(create_edge(
                        EdgeType.SUBSET_OF, sub_cat_node.id, category_nodes[parent_cat_name].id
                    ))
                break

    print("[DONE] Ontology seeded successfully!")
    engine.print_stats()
    return engine


def export_taxonomy_json(output_path: str = "data/ontology/skills_taxonomy.json"):
    """Export the taxonomy as JSON for reference."""
    output = {
        "categories": [],
        "skills": [],
        "relationships": {
            "subset_of": [],
            "related_to": []
        }
    }

    # Categories
    for cat_name, cat_data in SKILL_TAXONOMY.items():
        output["categories"].append({
            "name": cat_name,
            "category_enum": cat_data["category"],
            "description": cat_data["description"]
        })

    # Skills
    for cat_name, cat_data in SKILL_TAXONOMY.items():
        for skill_name, skill_desc in cat_data["skills"].items():
            output["skills"].append({
                "name": skill_name,
                "parent_category": cat_name,
                "description": skill_desc
            })

    # SUBSET_OF relationships (skill -> category)
    for cat_name, cat_data in SKILL_TAXONOMY.items():
        for skill_name in cat_data["skills"]:
            output["relationships"]["subset_of"].append({
                "child": skill_name,
                "parent": cat_name,
                "type": "skill_to_category"
            })

    # RELATED_TO relationships
    for skill_a, skill_b, strength in RELATED_SKILLS:
        output["relationships"]["related_to"].append({
            "source": skill_a,
            "target": skill_b,
            "strength": strength,
            "bidirectional": True
        })

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"[EXPORT] Taxonomy exported to: {output_path}")


if __name__ == "__main__":
    import sys

    # Export JSON taxonomy
    export_taxonomy_json()

    # Seed into graph
    engine = seed_ontology()

    # Save graph
    output_path = sys.argv[1] if len(sys.argv) > 1 else "data/graph_ontology.json"
    engine.save_json(output_path)
    print(f"\n[SAVE] Ontology graph saved to: {output_path}")