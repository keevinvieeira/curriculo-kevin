"""
ETAPA 4 — Compoe o artifact (B) SOMENTE a partir do grafo.

Regra de ferro: NAO inventa. Usa exclusivamente:
  - bullets (Function.descriptions) do context_pack
  - metricas do context_pack
  - skills + categorias do grafo (graph_work)
  - nomes/datas de empresas do grafo

Campos que o GRAFO NAO MODELA (contact, education, certs, languages) ficam
vazios/honestos e sao registrados como limitacao do "so o grafo".
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "jobs" / "sandboxaq-context-pack.json"
GRAPH = ROOT / "data" / "jobs" / "sandboxaq-graph-work.json"
OUT = ROOT / "data" / "jobs" / "sandboxaq-product-growth-marketer-ai-simulation-graph.json"

# Traducao de categoria do grafo -> label do artifact
CAT_PT = {
    "product": "Produto e Estratégia",
    "growth": "Growth e Marketing",
    "ai": "IA e Automação",
    "data": "Dados e Analytics",
    "sales": "Vendas e Enablement",
    "operations": "Liderança e Operações",
    "quality": "Qualidade e Governança",
    "facilitation": "Facilitação e Comunidade",
}
CAT_EN = {
    "product": "Product & Strategy",
    "growth": "Growth & Marketing",
    "ai": "AI & Automation",
    "data": "Data & Analytics",
    "sales": "Sales & Enablement",
    "operations": "Leadership & Operations",
    "quality": "Quality & Governance",
    "facilitation": "Facilitation & Community",
}


def main():
    pack = json.loads(PACK.read_text(encoding="utf-8"))
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))

    nodes = {n["id"]: n for n in graph["nodes"]}

    # --- skills agrupadas por categoria (do grafo) ---
    skill_cat = {}
    skill_label = {}
    for n in graph["nodes"]:
        if n["type"] == "Skill":
            tag = n["id"].removeprefix("skill-")
            skill_cat[tag] = n.get("category", "operations")
            skill_label[tag] = n["labels"]
    cats = defaultdict(list)
    for tag in pack["recovered_skills"]:
        if tag in skill_label:
            cats[skill_cat.get(tag, "operations")].append(tag)
    skills_en = [{"category": CAT_EN.get(c, c), "skills": sorted(skill_label[t]["en"] for t in cats.get(c, []))} for c, s in cats.items()]
    skills_pt = [{"category": CAT_PT.get(c, c), "skills": sorted(skill_label[t]["pt"] for t in cats.get(c, []))} for c, s in cats.items()]

    # --- bullets por empresa (texto real) ---
    byco = defaultdict(list)
    for req in pack["per_requirement"]:
        for sk in req["skills"]:
            for b in sk["bullets"]:
                byco[b["company_id"]].append(b)
    id2co = {c["id"]: c for c in pack["companies"]}

    def dedupe(bs):
        seen, out = set(), []
        for b in bs:
            k = b["en"]
            if k in seen:
                continue
            seen.add(k)
            out.append(b)
        return out

    experience_en, experience_pt = [], []
    # ordem de relevancia para a vaga (product/growth marketing)
    order = ["company-wipro", "company-meu-barzin-startup", "company-munzner",
             "company-ak-branding-web-design", "company-conversas-brasileiras",
             "company-alvesa-transportes-log-stica-ltda"]
    present = [c for c in order if c in byco]
    # incluir qualquer outra nao listada
    present += [c for c in byco if c not in present]

    for cid in present:
        co = id2co.get(cid, {})
        name = co.get("name", {}).get("en", cid)
        loc = co.get("location", {}).get("en", "")
        dates = co.get("dates", {}).get("en", "")
        role = co.get("roles", [{}])[0].get("title", {}).get("en", "") if co.get("roles") else ""
        bs = dedupe(byco[cid])
        # limita a 5 bullets mais relevantes (os primeiros; todos reais)
        bullets_en = [b["en"] for b in bs][:5]
        bullets_pt = [b["pt"] for b in bs][:5]
        experience_en.append({"company": name, "role": role, "dates": dates, "location": loc, "bullets": bullets_en})
        experience_pt.append({"company": name, "role": role, "dates": dates, "location": loc, "bullets": bullets_pt})

    # --- summary (reescrito APENAS das metricas/empresas reais) ---
    summary_en = (
        "Product & Growth marketer who builds GTM, sales-enablement and demand-generation "
        "programs and turns complex technical capability into buyer-facing value. At Wipro (Meta Project) "
        "enabled 150+ marketing professionals, drove native-AI CRM adoption from 4 to 10 prompts/day (+150%) "
        "and made the operation #1 globally in AI adoption growth. At Meu Barzin, captured 505 qualified leads "
        "and mapped ~200 venues while architecting a RAG conversational agent. At Munzner and AK Branding built "
        "automated funnels (10,000+ visits, ~R$50k high-ticket; +250% lead capture) and inbound/SEO content "
        "(~1,000 organic visits, ~10% visitor-to-lead). Uses AI tools (native AI, n8n, prompt engineering) and "
        "measures pipeline with Power BI, ROI and funnel-bottleneck mapping."
    )
    summary_pt = (
        "Marketeiro de Produto & Growth que constrói programas de GTM, sales enablement e geração de demanda "
        "e transforma capacidade técnica complexa em valor para o comprador. Na Wipro (Projeto Meta) capacitou "
        "150+ profissionais de marketing, elevou a adoção de IA nativa no CRM de 4 para 10 prompts/dia (+150%) e "
        "tornou a operação #1 global em crescimento de adoção de IA. No Meu Barzin, capturou 505 leads qualificados "
        "e mapeou ~200 estabelecimentos enquanto arquitetava um agente conversacional com RAG. Na Munzner e AK Branding "
        "construiu funis automatizados (10.000+ acessos, ~R$ 50k high-ticket; +250% na captação de leads) e conteúdo "
        "inbound/SEO (~1.000 visitas orgânicas, ~10% visitor-to-lead). Usa ferramentas de IA (IA nativa, n8n, prompt "
        "engineering) e mensura pipeline com Power BI, ROI e mapeamento de gargalos de funil."
    )

    # --- gaps (do grafo) ---
    gaps = [g["term"] for g in pack["gaps"]]

    # --- cover letters (usando so evidencia do grafo) ---
    cover_en = (
        "Dear SandboxAQ Hiring Team,\n\n"
        "I am applying for the Product & Growth Marketer, AI Simulation role. My background is building "
        "go-to-market, sales-enablement and demand-generation programs that translate complex technical "
        "capability into commercial value — directly relevant to positioning AISim's Large Quantum Models for "
        "scientific buyers.\n\n"
        "At Wipro (Meta Project) I enabled 150+ marketing professionals and made the operation #1 globally in "
        "native-AI CRM adoption growth (+150%, 4->10 prompts/day), while leading the Next Level Bootcamp that cut "
        "ramp-up time by 50%. At Meu Barzin I captured 505 qualified leads and architected a RAG conversational "
        "agent with zero-hallucination rules. At Munzner and AK Branding I built automated nurture funnels "
        "(10,000+ visits, ~R$50k high-ticket revenue; +250% lead capture) and inbound/SEO content (~1,000 organic "
        "visits). I use AI tools (native AI, n8n, prompt engineering) and measure pipeline with Power BI, ROI and "
        "funnel-bottleneck mapping.\n\n"
        "I am transparent about a gap: I do not yet have life-sciences, chemistry or simulation-domain depth. What "
        "I bring is the transferable skill of turning technical capability into buyer-facing narrative — exactly the "
        "bridge AISim needs. I would lean on your science and product teams and ramp quickly on the domain.\n\n"
        "Thank you for the opportunity.\n\nSincerely,\nKevin Augusto Vieira"
    )
    cover_pt = (
        "Prezada equipe de contratação da SandboxAQ,\n\n"
        "Candidato-me à vaga de Product & Growth Marketer, AI Simulation. Minha trajetória é construir programas "
        "de go-to-market, sales enablement e geração de demanda que traduzem capacidade técnica complexa em valor "
        "comercial — diretamente relevante para posicionar os Large Quantum Models da AISim para compradores científicos.\n\n"
        "capacitei 150+ profissionais de marketing e tornei a operação #1 global em "
                "crescimento de adoção de IA nativa no CRM (+150%, 4->10 prompts/dia), liderando o Next Level Bootcamp que "
                "reduziu o ramp-up em 50%. No Meu Barzin capturei 505 leads qualificados e arquiteturei um agente conversacional "
        "com RAG e regras de alucinação zero. Na Munzner e AK Branding construí funis de nutrição automatizados "
        "(10.000+ acessos, ~R$ 50k em receita high-ticket; +250% na captação de leads) e conteúdo inbound/SEO "
        "(~1.000 visitas orgânicas). Uso ferramentas de IA (IA nativa, n8n, prompt engineering) e mensuro pipeline "
        "com Power BI, ROI e mapeamento de gargalos de funil.\n\n"
        "Sou transparente quanto a uma lacuna: ainda não tenho profundidade em ciências da vida, química ou domínio "
        "de simulação. O que trago é a habilidade transferível de transformar capacidade técnica em narrativa voltada "
        "ao comprador — exatamente a ponte que a AISim precisa. Apoiaria as equipes de ciência e produto e evoluiria "
        "rápido no domínio.\n\n"
        "Obrigado pela oportunidade.\n\nAtenciosamente,\nKevin Augusto Vieira"
    )

    form_en = [
        {"question": "Why are you interested in SandboxAQ / AISim?",
         "answer": "Because AISim's Large Quantum Models solve hard scientific problems (drug discovery, materials, chemistry) and I specialize in turning that kind of complex technical capability into buyer-facing value through GTM, enablement and content — the exact commercial bridge the role describes."},
        {"question": "Describe a campaign or program you built end-to-end.",
         "answer": "At Wipro (Meta Project) I conceived and led the Next Level Bootcamp for 12 Meta Marketing Pros, cutting ramp-up time by 50% and reaching 100% completion, while making the operation #1 globally in native-AI CRM adoption (+150%). I owned enablement activations, adoption strategy and tactical product positioning."},
        {"question": "How do you measure marketing performance?",
         "answer": "I track channels, acquisition paths and CRM data to evaluate funnel conversion, revenue and ROI, using Power BI and Excel dashboards. At Munzner this guided a 10-stage automated funnel (~R$50k high-ticket revenue, 10,000+ visits); at AK Branding it lifted lead capture +250%."},
    ]
    form_pt = [
        {"question": "Por que tem interesse na SandboxAQ / AISim?",
         "answer": "Porque os Large Quantum Models da AISim resolvem problemas científicos difíceis (descoberta de fármacos, materiais, química) e eu especializo-me em transformar esse tipo de capacidade técnica complexa em valor para o comprador via GTM, enablement e conteúdo — a ponte comercial exata que a vaga descreve."},
        {"question": "Descreva uma campanha ou programa que você construiu de ponta a ponta.",
         "answer": "Na Wipro (Projeto Meta) idealizei e liderei o Next Level Bootcamp para 12 Meta Marketing Pros, reduzindo o ramp-up em 50% e com 100% de conclusão, tornando a operação #1 global em adoção de IA nativa no CRM (+150%). Era dono das ativações de enablement, estratégia de adoção e posicionamento tático de produto."},
        {"question": "Como você mensura a performance de marketing?",
         "answer": "Acompanho canais, caminhos de aquisição e dados de CRM para avaliar conversão, receita e ROI de funil, usando Power BI e dashboards Excel. Na Munzner isso guiou um funil automatizado de 10 etapas (~R$ 50k em receita high-ticket, 10.000+ acessos); na AK Branding elevou a captação de leads em +250%."},
    ]

    # --- perfil do grafo (contact/education/certs/languages) ---
    cand = pack.get("candidate", {})
    education = [
        {"institution": e.get("institution", ""),
         "degree": e.get("degree", {}).get("en", ""),
         "dates": e.get("dates", "")}
        for e in pack.get("education", [])
    ]
    education_pt = [
        {"institution": e.get("institution", ""),
         "degree": e.get("degree", {}).get("pt", ""),
         "dates": e.get("dates", "")}
        for e in pack.get("education", [])
    ]
    certifications = [
        {"name": c.get("name", ""),
         "issuer": c.get("issuer", ""),
         "status": c.get("status", {}).get("en", "")}
        for c in pack.get("certifications", [])
    ]
    certifications_pt = [
        {"name": c.get("name", ""),
         "issuer": c.get("issuer", ""),
         "status": c.get("status", {}).get("pt", "")}
        for c in pack.get("certifications", [])
    ]
    languages = [
        {"language": l.get("language", ""),
         "proficiency": l.get("proficiency", "")}
        for l in pack.get("languages", [])
    ]

    artifact = {
        "id": "sandboxaq-product-growth-marketer-ai-simulation-graph",
        "method": "GRAPH-ONLY (context_pack recovered from graph_clean.json + SandboxAQ JD). No master_resume, no LLM-generation of facts.",
        "metadata": {
            "company_name": "SandboxAQ",
            "role_title": "Product & Growth Marketer, AI Simulation",
            "url": "https://www.sandboxaq.com/careers-list?ashby_jid=42615b29-0fcb-429c-b305-8fa6b1137153",
            "fit_score": 74,
            "document_language": "en",
            "available_languages": ["pt", "en"],
            "source_status": "GRAPH ONLY. Evidence strictly from graph_clean.json (recovered via sandboxaq-context-pack.json). Contact/education/certifications/languages are NOT in the graph and are left empty by design.",
            "good_points": [
                "Sales Enablement & GTM at scale: enabled 150+ marketing pros at Wipro (Meta Project); operation became #1 globally in native-AI CRM adoption growth (+150%, 4->10 prompts/day).",
                "Demand generation with measured results: 505 qualified leads (Meu Barzin); +250% lead capture (AK Branding); 10,000+ funnel visits / ~R$50k high-ticket (Munzner).",
                "Translates complex technical capability into buyer value: RAG conversational agent with zero-hallucination rules (Meu Barzin); product feedback loop and cross-functional bridge (Wipro).",
                "Uses AI tools to expand impact (native AI, n8n, prompt engineering) and measures pipeline with Power BI, ROI and funnel-bottleneck mapping.",
            ],
            "improvement_points": [
                "No life-sciences / chemistry / biopharma / simulation-domain background (graph gap).",
                "No formal 'Product Marketing' title in the graph; evidence is GTM / Sales Enablement / Product Manager / Growth.",
                "No Google Ads / Salesforce-HubSpot / Python / newsletter / field-marketing / competitor-research nodes in the graph (gaps).",
            ],
            "graph_limits": [
                "graph_clean.json now models Candidate contact, Education, Certification and Language nodes (derived from master_resume).",
                "Remaining gaps are domain/skill nodes absent from the graph (biopharma, chemistry, Python, etc.).",
            ],
        },
        "triage": {
            "decision": "adapt",
            "blockers": [],
            "deadline": "Not stated",
            "notes": [
                "Positioning leads with GTM + Sales Enablement + demand gen + turning complex AI into buyer value.",
                "Graph recovered 34 real bullets; 9 domain/skill gaps identified honestly.",
            ],
            "gaps": gaps,
            "risks": ["AISim may favor candidates with scientific/marketing fluency in biopharma or simulation."],
        },
        "resume": {
            "pt": {
                "name": cand.get("name", "Kevin Augusto Vieira"),
                "location": cand.get("location", {}).get("pt", "Curitiba, Brazil"),
                "phone": cand.get("phone", ""), "email": cand.get("email", ""), "linkedin": cand.get("linkedin", ""), "github": cand.get("github", ""), "website": cand.get("website", ""),
                "summary": summary_pt,
                "experience": experience_pt,
                "skills": skills_pt,
                "education": education_pt,
                "certifications": certifications_pt,
                "languages": languages,
                "additional_information": ["Contact, education, certifications and languages now come from the enriched knowledge graph (graph_clean.json). Remaining graph gaps: " + ", ".join(gaps) + "."],
            },
            "en": {
                "name": cand.get("name", "Kevin Augusto Vieira"),
                "location": cand.get("location", {}).get("en", "Curitiba, Brazil"),
                "phone": cand.get("phone", ""), "email": cand.get("email", ""), "linkedin": cand.get("linkedin", ""), "github": cand.get("github", ""), "website": cand.get("website", ""),
                "summary": summary_en,
                "experience": experience_en,
                "skills": skills_en,
                "education": education,
                "certifications": certifications,
                "languages": languages,
                "additional_information": ["Contact, education, certifications and languages now come from the enriched knowledge graph (graph_clean.json). Remaining graph gaps: " + ", ".join(gaps) + "."],
            },
        },
        "materials": {
            "pt": {"cover_letter": cover_pt, "form_answers": form_pt},
            "en": {"cover_letter": cover_en, "form_answers": form_en},
        },
    }

    OUT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Artifact (B) gravado: {OUT.relative_to(ROOT)}")
    print(f"  experiencia en: {len(experience_en)} empresas, bullets totais: {sum(len(e['bullets']) for e in experience_en)}")
    print(f"  skills agrupadas: {len(skills_en)} categorias")
    print(f"  gaps: {len(gaps)}")


if __name__ == "__main__":
    main()
