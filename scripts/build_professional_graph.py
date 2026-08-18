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
        "business_model", "business_models", "discovery", "e_commerce", "experimentation",
        "learning", "monetization", "pricing", "product_architecture", "product_strategy",
        "ux", "ux_ui", "web_design", "web_development", "zero_to_one",
    },
    "growth": {
        "ab_testing", "acquisition", "ads", "agency_management", "branding", "content_creation",
        "content_marketing", "copywriting", "cro", "email_marketing", "funnel", "growth",
        "inbound", "infoproduct", "lead_generation", "marketing", "narratives", "paid_media",
        "seo", "social_media", "tripwire", "volume",
    },
    "ai": {"ai", "ai_implementation", "automation", "chatbots", "prompt_engineering"},
    "data": {
        "analytics", "data", "data_strategy", "metrics", "nocodb", "postgresql", "power_bi",
        "revenue_analytics", "roi", "sql", "supabase", "tracking", "web_scraping",
    },
    "sales": {
        "b2b", "business_development", "client_consulting", "coaching", "crm", "crm_enablement", "high_ticket",
        "methodology", "partnerships", "playbooks", "product_positioning", "sales",
        "sales_enablement", "technical_reference", "training",
    },
    "quality": {
        "bcp", "compliance", "documentation", "governance", "legal_research", "lgpd",
        "quality_assurance", "root_cause_analysis", "security", "technical_writing",
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
    "project_management": "Gestão de Projetos", "prompt_engineering": "Engenharia de Prompts",
    "quality_assurance": "Garantia de Qualidade", "ramp_up": "Ramp-up", "recruitment": "Recrutamento",
    "revenue_analytics": "Análise de Receita", "roadmap": "Roadmap", "roi": "ROI",
    "root_cause_analysis": "Análise de Causa Raiz", "sales": "Vendas",
    "sales_enablement": "Sales Enablement", "security": "Segurança", "seo": "SEO",
    "social_innovation": "Inovação Social", "social_media": "Mídias Sociais", "sql": "SQL",
    "squad": "Squad", "supabase": "Supabase", "support": "Suporte",
    "technical_reference": "Referência Técnica", "thinking_environment": "Thinking Environment",
    "technical_writing": "Redação Técnica",
    "timeline": "Cronograma", "tracking": "Rastreamento", "training": "Treinamento",
    "tripwire": "Oferta de Entrada", "ux": "Experiência do Usuário", "ux_ui": "UX/UI",
    "volume": "Volume de Entregas", "web_design": "Web Design", "web_development": "Desenvolvimento Web",
    "web_scraping": "Web Scraping", "zero_to_one": "Construção de 0 a 1",
}

EN_OVERRIDES = {
    "ab_testing": "A/B Testing", "admin": "Administration", "ai": "Artificial Intelligence",
    "b2b": "B2B", "bcp": "Business Continuity Planning", "crm": "CRM", "cro": "Conversion Optimization",
    "e_commerce": "E-commerce", "e_learning": "E-learning", "email_marketing": "Email Marketing",
    "high_ticket": "High Ticket", "lgpd": "LGPD", "nocodb": "NocoDB", "okr": "OKRs",
    "ops": "Operations", "pmo": "PMO", "postgresql": "PostgreSQL", "power_bi": "Power BI",
    "prompt_engineering": "Prompt Engineering", "roi": "ROI", "seo": "SEO", "sql": "SQL",
    "supabase": "Supabase", "ux": "User Experience", "ux_ui": "UX/UI", "web_scraping": "Web Scraping",
    "zero_to_one": "0-to-1 Building",
}

# Curated, source-linked outcomes. Values and descriptions come from the cited master bullet.
METRICS = {
    "Wipro": [
        (1, "150+", "profissionais capacitados", "professionals enabled"),
        (4, "+150%", "aumento no uso de IA", "increase in AI usage"),
        (4, "4 → 10", "prompts por dia", "prompts per day"),
        (4, "#1 global", "crescimento de adoção de IA", "AI adoption growth"),
        (8, "12", "consultores no piloto", "consultants in the pilot"),
        (8, "100%", "conclusão do bootcamp", "bootcamp completion"),
        (8, "-50%", "tempo de ramp-up", "ramp-up time"),
        (8, "90%+", "qualidade nas primeiras auditorias", "quality on initial audits"),
        (8, "90%", "CSAT dos consultores", "consultant CSAT"),
    ],
    "Meu Barzin (Startup)": [
        (2, "~200", "bares mapeados", "venues mapped"),
        (4, "505", "leads qualificados", "qualified leads"),
        (4, "2.000+", "seguidores no Instagram", "Instagram followers"),
        (4, "22,3%", "usuários altamente engajados", "highly engaged users"),
        (6, "43,9%", "abandono na primeira mensagem", "first-message dropout"),
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


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


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

        for role_index, role in enumerate(item["roles"]):
            role_id = f"role-{slug(company)}-{role_index + 1}"
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

        primary_role_id = f"role-{slug(company)}-1"
        for bullet_index, bullet in enumerate(item["bullets"], 1):
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
                "role_id": primary_role_id,
                "source": f"master_resume.json:work_experience:{slug(company)}:bullet:{bullet_index}",
                "size": 0.58,
                "color": "#22d3ee",
            })
            edges.append({"source": primary_role_id, "target": function_id, "type": "HAS_FUNCTION"})
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
        for metric_index, (bullet_index, value, name_pt, name_en) in enumerate(METRICS.get(company, []), 1):
            bullet = item["bullets"][bullet_index]
            metric_id = f"metric-{slug(company)}-{metric_index}"
            add_node({
                "id": metric_id,
                "type": "Metric",
                "labels": {"pt": value, "en": value.replace(",", ".")},
                "names": {"pt": name_pt, "en": name_en},
                "contexts": {"pt": bullet["pt"], "en": bullet["en"]},
                "company_id": company_id,
                "size": 0.52,
                "color": "#fbbf24",
            })
            edges.append({"source": company_id, "target": metric_id, "type": "HAS_METRIC"})

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
        },
    }


def main() -> None:
    with MASTER_PATH.open(encoding="utf-8") as file:
        master = json.load(file)
    graph = build_graph(master)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(graph, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(
        f"Built {OUTPUT_PATH.relative_to(ROOT)}: "
        f"{graph['stats']['total_nodes']} nodes / {graph['stats']['total_edges']} edges"
    )


if __name__ == "__main__":
    main()
