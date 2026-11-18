"""Build the professional graph projection from master_resume.json."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MASTER_PATH = ROOT / "master_resume.json"
OUTPUT_PATH = ROOT / "data" / "graph_clean.json"
TEMPLATE_PATH = ROOT / "graph-3d.html"
STATIC_SITE_PATH = ROOT / "docs" / "index.html"

CATEGORIES = {
    "product": {"pt": "Produto e Estratégia", "en": "Product & Strategy", "color": "#4a9eff"},
    "growth": {"pt": "Growth e Marketing", "en": "Growth & Marketing", "color": "#00d4aa"},
    "ai": {"pt": "IA e Automação", "en": "AI & Automation", "color": "#a855f7"},
    "data": {"pt": "Dados e Analytics", "en": "Data & Analytics", "color": "#ff8c42"},
    "sales": {"pt": "Vendas e Enablement", "en": "Sales & Enablement", "color": "#ef4444"},
    "operations": {"pt": "Liderança e Operações", "en": "Leadership & Operations", "color": "#38bdf8"},
    "quality": {"pt": "Qualidade e Governança", "en": "Quality & Governance", "color": "#f472b6"},
    "facilitation": {"pt": "Facilitação e Comunidade", "en": "Facilitation & Community", "color": "#34d399"},
}

CATEGORY_TAGS = {
    "product": {
        "business_model", "business_models", "case_study", "competitive_analysis", "customer_research",
        "discovery", "product_discovery", "product_management", "e_commerce", "experimentation",
        "fintech", "frontend", "healthcare", "learning", "mobile_first", "monetization", "offer_design",
        "ost", "portfolio", "positioning", "pricing", "prd", "product_architecture", "product_feedback",
        "product_strategy", "pwa", "react", "tool_stack", "typescript", "user_interviews", "ux", "ux_ui",
        "frictionless_ux", "voice_of_customer", "web_design", "web_development", "zero_to_one",
        "product_operations", "ats", "deterministic_ux", "spatial_ui", "interaction_design",
    },
    "growth": {
        "ab_testing", "acquisition", "ads", "agency_management", "branding", "content_creation",
        "content_marketing", "content_ops", "copywriting", "creatives", "cro", "email_marketing",
        "funnel", "growth", "gtm", "icp", "inbound", "infoproduct", "lead_generation", "local_seo",
        "marketing", "multichannel", "narratives", "packaging", "paid_media", "publishing", "referral",
        "remarketing", "segmentation", "seo", "social_media", "social_selling", "tripwire", "volume",
    },
    "ai": {
        "ai", "ai_agents", "ai_chat", "ai_implementation", "ai_tooling", "ai_workflows", "automation",
        "chatbots", "llm", "prompt_engineering", "rag", "rapid_prototyping", "research",
        "ai_personalization", "llm_orchestration", "graph_rag", "semantic_search",
        "skill_transferability", "prompt_governance", "ai_assisted_engineering", "match_engine",
    },
    "data": {
        "analytics", "data", "data_strategy", "database", "metrics", "nocodb", "postgresql", "power_bi",
        "realtime_data", "revenue_analytics", "roi", "sql", "supabase", "tracking", "web_scraping",
        "data_architecture", "ssot", "json_schema", "data_governance", "knowledge_graphs",
        "data_modeling", "graph_theory", "gap_analysis", "funnel_analytics",
    },
    "sales": {
        "b2b", "b2b_prospecting", "b2b_sales", "build_vs_buy", "business_development",
        "client_consulting", "coaching", "cost_reduction", "crm", "crm_enablement", "high_ticket",
        "lead_qualification", "methodology", "partnerships", "pipeline", "playbooks", "pmm",
        "product_positioning", "revops", "sales", "sales_enablement", "technical_reference",
        "training", "win_rate",
    },
    "operations": {
        "agile", "backlog", "budget", "cloudflare_pages", "cloudflare_workers", "coordination",
        "deployment", "devops", "docker", "finops", "infrastructure", "kanban", "nextjs", "okr",
        "ops", "performance", "pmo", "production", "project_management", "timeline",
    },
    "quality": {
        "ai_alignment", "ai_governance", "api_auth", "appsec", "bcp", "cloudflare_access",
        "compliance", "controls", "documentation", "governance", "legal_research", "lgpd",
        "quality_assurance", "responsible_ai", "root_cause_analysis", "sast", "security",
        "technical_writing", "uat",
    },
    "facilitation": {
        "art_of_hosting", "collective_intelligence", "community", "community_management",
        "facilitation", "social_innovation", "thinking_environment",
    },
}

PT_SKILLS = {
    "ab_testing": "Testes A/B", "acquisition": "Aquisição", "admin": "Administração",
    "ads": "Anúncios", "agency_management": "Gestão de Agência", "agile": "Métodos Ágeis",
    "ai": "Inteligência Artificial", "ai_implementation": "Implementação de IA",
    "analytics": "Análise de Dados", "art_of_hosting": "Art of Hosting",
    "automation": "Automação", "b2b": "B2B", "backlog": "Backlog",
    "bcp": "Plano de Continuidade de Negócios", "bootcamp": "Bootcamp",
    "branding": "Branding", "budget": "Orçamento", "business_development": "Desenvolvimento de Negócios",
    "business_model": "Modelo de Negócio", "business_models": "Modelos de Negócio",
    "chatbots": "Chatbots", "coaching": "Coaching", "collaboration": "Colaboração",
    "client_consulting": "Consultoria para Clientes",
    "collective_intelligence": "Inteligência Coletiva", "community": "Comunidade",
    "community_management": "Gestão de Comunidade", "compliance": "Compliance",
    "content_creation": "Criação de Conteúdo", "content_marketing": "Marketing de Conteúdo",
    "controls": "Controles", "coordination": "Coordenação", "copywriting": "Copywriting",
    "crm": "CRM", "crm_enablement": "Capacitação em CRM", "cro": "Otimização de Conversão",
    "cross_functional": "Colaboração Interfuncional", "data": "Dados",
    "data_strategy": "Estratégia de Dados", "discovery": "Discovery",
    "documentation": "Documentação", "e_commerce": "E-commerce", "e_learning": "Educação Digital",
    "email_marketing": "E-mail Marketing", "experimentation": "Experimentação",
    "facilitation": "Facilitação", "finance": "Finanças", "funnel": "Funil",
    "governance": "Governança", "growth": "Growth", "high_ticket": "High Ticket",
    "inbound": "Inbound Marketing", "infoproduct": "Infoproduto", "lead_generation": "Geração de Leads",
    "leadership": "Liderança", "learning": "Aprendizado", "lgpd": "LGPD",
    "legal_research": "Pesquisa Legal",
    "logistics": "Logística", "marketing": "Marketing", "methodology": "Metodologia",
    "metrics": "Métricas", "monetization": "Monetização", "narratives": "Narrativas",
    "nocodb": "NocoDB", "okr": "OKRs", "ops": "Operações", "paid_media": "Mídia Paga",
    "partnerships": "Parcerias", "playbooks": "Playbooks", "pmo": "PMO",
    "postgresql": "PostgreSQL", "power_bi": "Power BI", "pricing": "Precificação",
    "prioritization": "Priorização", "product_architecture": "Arquitetura de Produto",
    "product_positioning": "Posicionamento de Produto", "product_strategy": "Estratégia de Produto",
    "product_feedback": "Feedback de Produto",
    "project_management": "Gestão de Projetos", "prompt_engineering": "Engenharia de Prompts",
    "quality_assurance": "Garantia de Qualidade", "ramp_up": "Ramp-up", "recruitment": "Recrutamento",
    "revenue_analytics": "Análise de Receita", "roadmap": "Roadmap", "roi": "ROI",
    "root_cause_analysis": "Análise de Causa Raiz", "sales": "Vendas",
    "sales_enablement": "Sales Enablement", "security": "Segurança", "seo": "SEO",
    "social_innovation": "Inovação Social", "social_media": "Mídias Sociais", "sql": "SQL",
    "squad": "Squad", "supabase": "Supabase", "support": "Suporte",
    "prd": "Arquitetura de Requisitos / PRD", "product_discovery": "Product Discovery",
    "rapid_prototyping": "Prototipação Acelerada", "realtime_data": "Dados em Tempo Real",
    "database": "Banco de Dados", "frictionless_ux": "Design Anti-Atrito", "uat": "Testes de Aceitação (UAT)",
    "technical_reference": "Referência Técnica", "thinking_environment": "Thinking Environment",
    "technical_writing": "Redação Técnica",
    "timeline": "Cronograma", "tracking": "Rastreamento", "training": "Treinamento",
    "tripwire": "Oferta de Entrada", "ux": "Experiência do Usuário", "ux_ui": "UX/UI",
    "volume": "Volume de Entregas", "web_design": "Web Design", "web_development": "Desenvolvimento Web",
    "voice_of_customer": "Voz do Usuário", "web_scraping": "Web Scraping", "zero_to_one": "Construção de 0 a 1",
    "data_architecture": "Data Architecture", "ssot": "Single Source of Truth", 
    "json_schema": "JSON Schema", "data_governance": "Data Governance", 
    "match_engine": "Match Engine", "gap_analysis": "Gap Analysis", 
    "semantic_search": "Semantic Search", "ai_personalization": "AI Personalization", 
    "llm_orchestration": "LLM Orchestration", "document_engineering": "Document Engineering", 
    "html_css": "HTML/CSS", "ats_optimization": "ATS Optimization", 
    "internationalization": "Internacionalização (PT/EN)", "product_operations": "Product Operations", 
    "funnel_analytics": "Funnel Analytics", "ats": "Sistemas ATS", 
    "knowledge_graphs": "Knowledge Graphs", "data_modeling": "Data Modeling", 
    "graph_theory": "Graph Theory", "graph_rag": "GraphRAG", 
    "skill_transferability": "Skill Transferability", "python": "Python", 
    "webgl": "WebGL", "three_js": "Three.js", "spatial_ui": "Spatial UI", 
    "interaction_design": "Interaction Design", "deterministic_ux": "Navegação Determinística", 
    "ai_assisted_engineering": "Vibe Coding (AI Engineering)", "prompt_governance": "Prompt Governance", 
    "ci_cd": "CI/CD Online-First", "test_automation": "Test Automation",
    "ai_agents": "Agentes de IA", "ai_alignment": "Alinhamento de IA",
    "ai_chat": "Chat com IA", "ai_governance": "Governança de IA",
    "ai_tooling": "Tooling Agêntico", "ai_workflows": "Fluxos com IA",
    "api_auth": "Autenticação de API", "appsec": "AppSec",
    "b2b_prospecting": "Prospecção B2B", "b2b_sales": "Vendas B2B",
    "build_vs_buy": "Build vs. Buy", "case_study": "Case Study",
    "cloudflare_access": "Cloudflare Access", "cloudflare_pages": "Cloudflare Pages",
    "cloudflare_workers": "Cloudflare Workers", "competitive_analysis": "Análise Competitiva",
    "content_ops": "Operação Editorial (Content Ops)", "cost_reduction": "Redução de Custos",
    "creatives": "Criativos de Alta Conversão", "customer_research": "Pesquisa com Usuários",
    "deployment": "Deploy em Nuvem", "devops": "DevOps",
    "docker": "Docker", "finops": "FinOps (Custos IA)",
    "fintech": "FinTech", "frontend": "Engenharia Frontend",
    "gtm": "Go-to-Market (GTM)", "healthcare": "HealthTech & Clínicas",
    "icp": "Definição de ICP", "infrastructure": "Infraestrutura Cloud/VPS",
    "kanban": "Kanban", "lead_qualification": "Qualificação de Leads",
    "llm": "LLMs (Modelos de Linguagem)", "local_seo": "SEO Local",
    "mobile_first": "Design Mobile-First", "multichannel": "Operação Multicanal",
    "nextjs": "Next.js", "offer_design": "Design de Oferta",
    "ost": "Opportunity Solution Tree (OST)", "packaging": "Empacotamento de Oferta",
    "performance": "Performance Web", "pipeline": "Gestão de Pipeline",
    "pmm": "Product Marketing (PMM)", "portfolio": "Portfólio de Produto",
    "positioning": "Posicionamento", "product_management": "Product Management",
    "production": "Sistemas em Produção", "publishing": "Publicação Digital",
    "pwa": "PWA (Progressive Web App)", "rag": "Arquitetura RAG",
    "react": "React", "referral": "Aquisição por Indicação",
    "remarketing": "Remarketing", "research": "Pesquisa Aplicada",
    "responsible_ai": "IA Responsável", "revops": "Revenue Operations (RevOps)",
    "sast": "SAST (Análise Estática)", "segmentation": "Segmentação",
    "social_selling": "Social Selling", "tool_stack": "Arquitetura de Tool Stack",
    "typescript": "TypeScript", "user_interviews": "Entrevistas com Usuários",
    "win_rate": "Win Rate",
}

EN_OVERRIDES = {
    "ab_testing": "A/B Testing", "admin": "Administration", "ai": "Artificial Intelligence",
    "ai_agents": "AI Agents", "ai_alignment": "AI Alignment", "ai_chat": "Conversational AI Chat",
    "ai_governance": "AI Governance", "ai_tooling": "Agentic AI Tooling", "ai_workflows": "AI Workflows",
    "api_auth": "API Authentication", "appsec": "AppSec", "b2b": "B2B",
    "b2b_prospecting": "B2B Prospecting", "b2b_sales": "B2B Sales",
    "bcp": "Business Continuity Planning", "build_vs_buy": "Build vs. Buy",
    "content_ops": "Content Operations", "crm": "CRM", "cro": "Conversion Optimization",
    "devops": "DevOps", "e_commerce": "E-commerce", "e_learning": "E-learning",
    "email_marketing": "Email Marketing", "finops": "FinOps (AI Cost Routing)",
    "fintech": "FinTech", "frontend": "Frontend Engineering", "gtm": "Go-to-Market (GTM)",
    "healthcare": "Healthcare Systems", "high_ticket": "High Ticket", "icp": "ICP Definition",
    "lgpd": "LGPD", "llm": "LLMs", "local_seo": "Local SEO",
    "mobile_first": "Mobile-First Design", "multichannel": "Multi-Channel Operations",
    "nextjs": "Next.js", "nocodb": "NocoDB", "okr": "OKRs", "ops": "Operations",
    "ost": "Opportunity Solution Tree (OST)", "performance": "Web Performance",
    "pmm": "Product Marketing (PMM)", "pmo": "PMO", "postgresql": "PostgreSQL",
    "power_bi": "Power BI", "prd": "PRD & Requirements Architecture",
    "product_discovery": "Product Discovery", "publishing": "Digital Publishing",
    "pwa": "PWA", "rag": "RAG Architecture", "rapid_prototyping": "Rapid Prototyping",
    "realtime_data": "Real-Time Data Architecture", "research": "Applied Research",
    "revops": "Revenue Operations (RevOps)", "database": "Database Architecture",
    "frictionless_ux": "Frictionless UX Design", "sast": "SAST (Static Security Analysis)",
    "uat": "User Acceptance Testing (UAT)", "prompt_engineering": "Prompt Engineering",
    "roi": "ROI", "seo": "SEO", "sql": "SQL", "supabase": "Supabase",
    "typescript": "TypeScript", "ux": "User Experience", "ux_ui": "UX/UI",
    "web_scraping": "Web Scraping", "voice_of_customer": "Voice of Customer",
    "zero_to_one": "0-to-1 Building",
}

# Curated, source-linked outcomes. Values and descriptions come from the cited master bullet.
METRICS = {
    "AI Builder — Projetos de Produtos": [
        # AI Career OS
        ("ai-career-os-b01", "100%", "governança SSOT sem alucinação", "zero-hallucination SSOT governance"),
        ("ai-career-os-b02", ">95%", "precisão do Fit Score no Match Engine", "Match Engine Fit Score accuracy"),
        ("ai-career-os-b09", "0 Saltos", "navegação determinística sem quebra de hierarquia", "deterministic navigation without hierarchy breakage"),
        ("ai-career-os-b10", "+10x", "aceleração no ciclo de engenharia com IA", "engineering cycle speedup with AI"),
        # CRM Odontológico com IA
        ("crm-odonto-b01", "24/7", "atendimento e agendamento no WhatsApp", "24/7 WhatsApp AI patient scheduling"),
        ("crm-odonto-b03", "~85%", "redução de custo de stack (US$ 14-18/mês)", "stack cost reduction (US$ 14-18/mo)"),
        ("crm-odonto-b04", "8 etapas", "funil clínico Kanban self-hosted", "self-hosted clinical Kanban pipeline"),
        # Bússola da Rotina
        ("bussola-da-rotina-b01", "0→1", "concepção de metodologia autoral", "0-to-1 methodology conception"),
        ("bussola-da-rotina-b02", "+10x", "velocidade de desenvolvimento vs tradicional", "development velocity vs traditional"),
        ("bussola-da-rotina-b02", ">95%", "economia de custos de engenharia", "engineering cost savings"),
        ("bussola-da-rotina-b02", "5.700+", "linhas de código em SPA nativa", "lines of code in native SPA"),
        ("bussola-da-rotina-b03", "100%", "estabilidade de dados em tempo real", "real-time data stability"),
        # Meu Barzin
        ("meu-barzin-b03", "~200", "bares mapeados via web scraping", "venues mapped via web scraping"),
        ("meu-barzin-b05", "505", "leads qualificados capturados", "qualified leads captured"),
        ("meu-barzin-b05", "2.000+", "seguidores no Instagram", "Instagram followers"),
        ("meu-barzin-b05", "22,3%", "usuários altamente engajados", "highly engaged users"),
        ("meu-barzin-b07", "43,9%", "abandono na primeira mensagem (otimizado)", "first-message dropout (optimized)"),
        # Yamas & Niyamas AI
        ("yamas-niyamas-ai-b01", "13", "fichamentos em alinhamento e abstenção RAG", "AI alignment & RAG abstention syntheses"),
    ],
    "Wipro": [
        (1, "150+", "profissionais capacitados", "professionals enabled"),
        (4, "+150%", "aumento no uso de IA", "increase in AI usage"),
        (4, "4 → 10", "prompts por dia", "prompts per day"),
        (4, "#1 global", "crescimento de adoção de IA", "AI adoption growth"),
        (9, "12", "consultores no piloto", "consultants in the pilot"),
        (9, "100%", "conclusão do bootcamp", "bootcamp completion"),
        (9, "-50%", "tempo de ramp-up", "ramp-up time"),
        (9, "90%+", "qualidade nas primeiras auditorias", "quality on initial audits"),
        (9, "90%", "CSAT dos consultores", "consultant CSAT"),
    ],
    "AK Branding & Web Design": [
        (0, "40+", "projetos entregues", "projects delivered"),
        (0, "2 / 3 meses", "contratos de alto valor", "high-value contracts"),
        (1, "+250%", "aumento na captação de leads", "increase in lead capture"),
        (1, "5 / dia", "leads qualificados", "qualified leads"),
        (3, "R$ 10.000", "receita em três meses", "revenue in three months"),
        (4, "100%", "projetos com conformidade LGPD", "projects with LGPD compliance"),
    ],
    "Munzner": [
        (0, "50", "vendas em dois meses", "sales in two months"),
        (0, "1,0x–1,5x", "ROI do produto de entrada", "tripwire ROI"),
        (1, "~R$ 50 mil", "receita high-ticket", "high-ticket revenue"),
        (1, "10.000+", "acessos no funil", "funnel visits"),
        (1, "10", "matrículas high-ticket", "high-ticket enrollments"),
        (3, "~1.000", "visitas orgânicas", "organic visits"),
        (3, "~100", "leads qualificados", "qualified leads"),
        (3, "~10%", "conversão visitante-lead", "visitor-to-lead conversion"),
    ],
    "Conversas Brasileiras": [
        (2, "5", "edições realizadas", "event editions"),
        (2, "20", "participantes por encontro", "participants per event"),
        (2, "~100", "pessoas engajadas", "people engaged"),
    ],
}


import unicodedata

def slug(value: str) -> str:
    nfkd = unicodedata.normalize('NFKD', value)
    ascii_val = nfkd.encode('ASCII', 'ignore').decode('ASCII')
    return re.sub(r"[^a-z0-9]+", "-", ascii_val.casefold()).strip("-")


def english_label(tag: str) -> str:
    return EN_OVERRIDES.get(tag, tag.replace("_", " ").title())


def category_for(tag: str) -> str:
    for category, tags in CATEGORY_TAGS.items():
        if tag in tags:
            return category
    return "operations"


def function_title(text: str) -> str:
    title = text.split(":", 1)[0] if ":" in text else text.split(".", 1)[0]
    return title if len(title) <= 72 else f"{title[:69].rstrip()}..."


def build_graph(master: dict[str, Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    skill_companies: dict[str, set[str]] = defaultdict(set)
    skill_evidence: Counter[tuple[str, str]] = Counter()
    skill_functions: dict[str, set[str]] = defaultdict(set)

    def add_node(node: dict[str, Any]) -> None:
        if node["id"] in node_ids:
            raise ValueError(f"Duplicate node id: {node['id']}")
        node_ids.add(node["id"])
        nodes.append(node)

    add_node({
        "id": "candidate",
        "type": "Candidate",
        "labels": {"pt": master["personal_info"]["name"], "en": master["personal_info"]["name"]},
        "size": 2.0,
        "color": "#ffffff",
        "glow": True,
    })

    work = master["work_experience"]
    company_ids = {item["company"]: f"company-{slug(item['company'])}" for item in work}

    for item in work:
        company = item["company"]
        company_id = company_ids[company]
        primary_dates = item["roles"][0]["dates"]
        add_node({
            "id": company_id,
            "type": "Company",
            "labels": {"pt": company, "en": company},
            "location": item["location"],
            "dates": primary_dates,
            "size": 1.5,
            "color": "#60a5fa",
            "glow": True,
        })
        edges.append({"source": "candidate", "target": company_id, "type": "WORKED_AT"})

        # Process Projects if present
        project_role_master_ids = {
            "proj-ai-career-os": "ai-builder-role-01",
            "proj-bussola-da-rotina": "ai-builder-role-02",
            "proj-meu-barzin": "ai-builder-role-03",
            "proj-crm-odonto": "ai-builder-role-04",
            "proj-wellness-protocol": "ai-builder-role-05",
            "proj-site-ebv": "ai-builder-role-06",
            "proj-e-prognus": "ai-builder-role-07",
            "proj-product-lead-os": "ai-builder-role-08",
            "proj-yamas-niyamas-ai": "ai-builder-role-09",
            "proj-fincasal-ai": "ai-builder-role-10",
            "proj-agentic-tooling-and-seo": "ai-builder-role-11",
        }
        proj_master_to_node: dict[str, str] = {}
        bullet_to_proj_master: dict[str, str] = {}
        if "projects" in item:
            for proj in item["projects"]:
                proj_id = f"project-{slug(proj['name'])}"
                proj_master_to_node[proj["id"]] = proj_id
                for pb in proj.get("bullets", []):
                    if pb.get("id"):
                        bullet_to_proj_master[pb["id"]] = proj["id"]
                add_node({
                    "id": proj_id,
                    "type": "Project",
                    "labels": {"pt": proj["name"], "en": proj["name"]},
                    "descriptions": proj.get("description", {}),
                    "url": proj.get("url", ""),
                    "company_id": company_id,
                    "size": 1.1,
                    "color": "#10b981",
                    "glow": True,
                })
                edges.append({"source": company_id, "target": proj_id, "type": "HAS_PROJECT"})

        role_master_to_node: dict[str, str] = {}
        for role_index, role in enumerate(item["roles"]):
            role_id = f"role-{slug(company)}-{role_index + 1}"
            if role.get("id"):
                role_master_to_node[role["id"]] = role_id
            add_node({
                "id": role_id,
                "type": "Role",
                "labels": role["title"],
                "dates": role["dates"],
                "company_id": company_id,
                "size": 0.72,
                "color": "#a78bfa",
            })
            edges.append({"source": company_id, "target": role_id, "type": "HAS_ROLE"})

        if company == "AI Builder — Projetos de Produtos":
            for proj_master_id, role_master_id in project_role_master_ids.items():
                p_node = proj_master_to_node.get(proj_master_id)
                r_node = role_master_to_node.get(role_master_id)
                if p_node and r_node:
                    edges.append({"source": p_node, "target": r_node, "type": "HAS_ROLE"})

        combined_bullets: list[dict[str, Any]] = list(item["bullets"])
        seen_bullet_ids = {b.get("id") for b in combined_bullets if b.get("id")}
        for proj in item.get("projects", []):
            for pb in proj.get("bullets", []):
                pb_id = pb.get("id")
                if pb_id and pb_id not in seen_bullet_ids:
                    combined_bullets.append(pb)
                    seen_bullet_ids.add(pb_id)

        primary_role_id = f"role-{slug(company)}-1"
        if "bullet_lookup" not in locals():
            bullet_lookup: dict[tuple[str, Any], tuple[str, str, str | None, dict[str, Any]]] = {}

        for bullet_index, bullet in enumerate(combined_bullets, 1):
            b_id = bullet.get("id", "")
            if company == "AI Builder — Projetos de Produtos":
                proj_master_id = bullet_to_proj_master.get(b_id)
                current_proj_id = proj_master_to_node.get(proj_master_id) if proj_master_id else None
                role_master_id = project_role_master_ids.get(proj_master_id or "")
                current_role_id = role_master_to_node.get(role_master_id, primary_role_id)
            else:
                current_role_id = primary_role_id
                current_proj_id = None

            function_id = f"function-{slug(company)}-{bullet_index}"
            add_node({
                "id": function_id,
                "type": "Function",
                "labels": {
                    "pt": function_title(bullet["pt"]),
                    "en": function_title(bullet["en"]),
                },
                "descriptions": {"pt": bullet["pt"], "en": bullet["en"]},
                "company_id": company_id,
                "role_id": current_role_id,
                "source": f"master_resume.json:work_experience:{slug(company)}:bullet:{bullet_index}",
                "size": 0.58,
                "color": "#22d3ee",
            })
            edges.append({"source": current_role_id, "target": function_id, "type": "HAS_FUNCTION"})
            if current_proj_id:
                edges.append({"source": current_proj_id, "target": function_id, "type": "HAS_FUNCTION"})

            info = (function_id, current_role_id, current_proj_id, bullet)
            bullet_lookup[(company, bullet_index - 1)] = info
            if b_id:
                bullet_lookup[(company, b_id)] = info

            for tag in set(bullet["tags"]):
                if tag not in PT_SKILLS:
                    raise ValueError(f"Missing PT skill label for tag: {tag}")
                skill_companies[tag].add(company_id)
                skill_evidence[(tag, company_id)] += 1
                skill_functions[tag].add(function_id)

    for tag in sorted(skill_companies):
        category = category_for(tag)
        category_data = CATEGORIES[category]
        skill_id = f"skill-{slug(tag)}"
        companies = sorted(skill_companies[tag])
        evidence_by_company = {
            company_id: skill_evidence[(tag, company_id)] for company_id in companies
        }
        add_node({
            "id": skill_id,
            "type": "Skill",
            "labels": {"pt": PT_SKILLS[tag], "en": english_label(tag)},
            "category": category,
            "category_labels": {"pt": category_data["pt"], "en": category_data["en"]},
            "companies": companies,
            "evidence_by_company": evidence_by_company,
            "evidence_count": sum(evidence_by_company.values()),
            "function_ids": sorted(skill_functions[tag]),
            "size": 0.5 + min(sum(evidence_by_company.values()), 4) * 0.08,
            "color": category_data["color"],
        })
        for company_id in companies:
            edges.append({
                "source": company_id,
                "target": skill_id,
                "type": "DEMONSTRATES",
                "evidence_count": evidence_by_company[company_id],
            })
        for function_id in sorted(skill_functions[tag]):
            edges.append({"source": function_id, "target": skill_id, "type": "DEMONSTRATES_SKILL"})

    for item in work:
        company = item["company"]
        company_id = company_ids[company]
        for metric_index, (bullet_ref, value, name_pt, name_en) in enumerate(METRICS.get(company, []), 1):
            function_id, current_role_id, current_proj_id, bullet = bullet_lookup[(company, bullet_ref)]

            metric_id = f"metric-{slug(company)}-{metric_index}"
            add_node({
                "id": metric_id,
                "type": "Metric",
                "labels": {"pt": value, "en": value.replace(",", ".")},
                "names": {"pt": name_pt, "en": name_en},
                "contexts": {"pt": bullet["pt"], "en": bullet["en"]},
                "company_id": company_id,
                "role_id": current_role_id,
                "size": 0.52,
                "color": "#fbbf24",
            })
            edges.append({"source": company_id, "target": metric_id, "type": "HAS_METRIC"})
            edges.append({"source": current_role_id, "target": metric_id, "type": "HAS_METRIC"})
            if current_proj_id:
                edges.append({"source": current_proj_id, "target": metric_id, "type": "HAS_METRIC"})
            edges.append({"source": function_id, "target": metric_id, "type": "PRODUCED_METRIC"})

    # --- Perfil do candidato: contact + education + certifications + languages ---
    # Tudo derivado do master_resume (fonte unica de verdade). Nao inventa.
    pi = master.get("personal_info", {})
    cand_node = nodes[0]
    cand_node["labels"] = {"pt": pi.get("name", "Kevin"), "en": pi.get("name", "Kevin")}
    cand_node["location"] = pi.get("location", {})
    cand_node["phone"] = pi.get("phone", "")
    cand_node["email"] = pi.get("email", "")
    cand_node["linkedin"] = pi.get("linkedin", "")
    cand_node["github"] = pi.get("github", "")
    cand_node["website"] = pi.get("website", "")

    for edu_index, edu in enumerate(master.get("education", []), 1):
        edu_id = f"edu-{edu_index}"
        degree = edu.get("degree", {})
        add_node({
            "id": edu_id,
            "type": "Education",
            "labels": {"pt": degree.get("pt", ""), "en": degree.get("en", "")},
            "institution": edu.get("institution", ""),
            "dates": edu.get("dates", ""),
            "size": 0.7,
            "color": "#f472b6",
        })
        edges.append({"source": "candidate", "target": edu_id, "type": "HAS_EDUCATION"})

    for cert_index, cert in enumerate(master.get("certifications", []), 1):
        cert_id = f"cert-{cert_index}"
        name = cert.get("name", "")
        add_node({
            "id": cert_id,
            "type": "Certification",
            "labels": {"pt": name, "en": name},
            "issuer": cert.get("issuer", ""),
            "status": cert.get("status", {}),
            "size": 0.6,
            "color": "#34d399",
        })
        edges.append({"source": "candidate", "target": cert_id, "type": "HAS_CERTIFICATION"})

    for lang_index, lang in enumerate(master.get("languages", {}).get("en", []), 1):
        lang_id = f"lang-{lang_index}"
        add_node({
            "id": lang_id,
            "type": "Language",
            "labels": {"pt": master.get("languages", {}).get("pt", [{}])[lang_index - 1].get("language", ""),
                       "en": lang.get("language", "")},
            "proficiency": lang.get("proficiency", ""),
            "size": 0.5,
            "color": "#38bdf8",
        })
        edges.append({"source": "candidate", "target": lang_id, "type": "HAS_LANGUAGE"})

    for edge in edges:
        if edge["source"] not in node_ids or edge["target"] not in node_ids:
            raise ValueError(f"Edge references unknown node: {edge}")

    return {
        "source": "master_resume.json",
        "nodes": nodes,
        "edges": edges,
        "categories": CATEGORIES,
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "total_skills": sum(node["type"] == "Skill" for node in nodes),
            "total_companies": sum(node["type"] == "Company" for node in nodes),
            "total_metrics": sum(node["type"] == "Metric" for node in nodes),
            "total_roles": sum(node["type"] == "Role" for node in nodes),
            "total_functions": sum(node["type"] == "Function" for node in nodes),
            "total_education": sum(node["type"] == "Education" for node in nodes),
            "total_certifications": sum(node["type"] == "Certification" for node in nodes),
            "total_languages": sum(node["type"] == "Language" for node in nodes),
            },
    }


def build_static_site(graph: dict[str, Any]) -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    if "__GRAPH_DATA__" not in template:
        raise ValueError("graph-3d.html does not contain the graph data placeholder")
    payload = json.dumps(graph, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    rendered = template.replace("__GRAPH_DATA__", payload)
    STATIC_SITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATIC_SITE_PATH.write_text(rendered, encoding="utf-8")


def main() -> None:
    with MASTER_PATH.open(encoding="utf-8") as file:
        master = json.load(file)
    graph = build_graph(master)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(graph, file, ensure_ascii=False, indent=2)
        file.write("\n")
    build_static_site(graph)
    print(
        f"Built {OUTPUT_PATH.relative_to(ROOT)}: "
        f"{graph['stats']['total_nodes']} nodes / {graph['stats']['total_edges']} edges"
    )
    print(f"Built {STATIC_SITE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
