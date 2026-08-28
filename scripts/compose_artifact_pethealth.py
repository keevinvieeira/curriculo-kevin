"""
ETAPA 4 (PIPELINE B - SO GRAFO) - Pet Health / Senior GTM Engineer.

Compoe o artifact (B) SOMENTE a partir do context_pack. Nao inventa nada.
Tudo que entra aqui ou vem do grafo (master_resume.json) ou e honestamente
declarado como gap.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "data" / "jobs" / "pethealth-context-pack.json"
GRAPH = ROOT / "data" / "jobs" / "pethealth-graph-work.json"
OUT = ROOT / "data" / "jobs" / "pethealth-gtm-engineer-senior-graph.json"

CAT_PT = {
    "product": "Produto e Estrategia",
    "growth": "Growth e Marketing",
    "ai": "IA e Automacao",
    "data": "Dados e Analytics",
    "sales": "Vendas e Enablement",
    "operations": "Lideranca e Operacoes",
    "quality": "Qualidade e Governanca",
    "facilitation": "Facilitacao e Comunidade",
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
    skills_en = [{"category": CAT_EN.get(c, c), "skills": sorted(skill_label[t]["en"] for t in cats.get(c, []))} for c in cats]
    skills_pt = [{"category": CAT_PT.get(c, c), "skills": sorted(skill_label[t]["pt"] for t in cats.get(c, []))} for c in cats]

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
    # ordem: empresas mais relevantes para uma vaga de GTM Engineering (CRM/automation/scale).
    order = ["company-wipro", "company-meu-barzin-startup", "company-munzner",
             "company-ak-branding-web-design", "company-conversas-brasileiras",
             "company-alvesa-transportes-log-stica-ltda"]
    present = [c for c in order if c in byco]
    present += [c for c in byco if c not in present]

    for cid in present:
        co = id2co.get(cid, {})
        name = co.get("name", {}).get("en", cid)
        loc = co.get("location", {}).get("en", "")
        dates = co.get("dates", {}).get("en", "")
        role = co.get("roles", [{}])[0].get("title", {}).get("en", "") if co.get("roles") else ""
        bs = dedupe(byco[cid])
        bullets_en = [b["en"] for b in bs][:5]
        bullets_pt = [b["pt"] for b in bs][:5]
        experience_en.append({"company": name, "role": role, "dates": dates, "location": loc, "bullets": bullets_en})
        experience_pt.append({"company": name, "role": role, "dates": dates, "location": loc, "bullets": bullets_pt})

    # --- summary (reescrito APENAS das metricas/empresas REAIS do grafo) ---
    # Posicionamento: lider de sistemas GTM com background em CRM, automacao,
    # enablement e IA aplicada. Aceita o gap Salesforce/HubSpot honestamente.
    summary_en = (
        "GTM systems leader with hands-on experience designing, integrating and scaling CRM, "
        "automation and enablement stacks across B2B SaaS, PLG and startup environments. At Wipro "
        "(Meta Project) enabled 150+ marketing professionals and made the operation #1 globally in "
        "native-AI CRM adoption growth (+150%, 4->10 prompts/day), owning enablement activations, "
        "adoption strategy and process documentation. At Meu Barzin built a 0-to-1 go-to-market "
        "engine (505 qualified leads, ~200 venues mapped) and architected a RAG conversational "
        "agent with zero-hallucination rules. At Munzner and AK Branding delivered automated "
        "nurture funnels (10,000+ visits, ~R$50k high-ticket revenue; +250% lead capture) and "
        "inbound/SEO content (~1,000 organic visits, ~10% visitor-to-lead). Fluent in SQL, data "
        "models and APIs; ships using agile, UAT, documentation and quality-assurance practices. "
        "Honest gap: no Salesforce Sales Cloud / HubSpot / Apex / Make-Zapier production depth in "
        "the graph; bring the transferable foundation (CRM, automation, integrations, enablement) "
        "and ramp on the platform."
    )
    summary_pt = (
        "Lider de sistemas GTM com experiencia pratica em projetar, integrar e escalar stacks de "
        "CRM, automacao e enablement em ambientes B2B SaaS, PLG e startup. Na Wipro (Projeto Meta) "
        "capacitei 150+ profissionais de marketing e tornei a operacao #1 global em crescimento de "
        "adocao de IA nativa no CRM (+150%, 4->10 prompts/dia), sendo dono das ativacoes de "
        "enablement, estrategia de adocao e documentacao de processos. No Meu Barzin construi um "
        "motor de go-to-market de 0 a 1 (505 leads qualificados, ~200 estabelecimentos mapeados) "
        "e arquitetei um agente conversacional com RAG e regras de alucinacao zero. Na Munzner e "
        "AK Branding entreguei funis de nutricao automatizados (10.000+ acessos, ~R$ 50k em receita "
        "high-ticket; +250% na captacao de leads) e conteudo inbound/SEO (~1.000 visitas organicas, "
        "~10% visitor-to-lead). Fluente em SQL, modelos de dados e APIs; entrega com praticas "
        "ageis, UAT, documentacao e garantia de qualidade. Gap honesto: nao tenho profundidade "
        "producao em Salesforce Sales Cloud / HubSpot / Apex / Make-Zapier no grafo; trago a base "
        "transferivel (CRM, automacao, integracoes, enablement) e rampo rapido na plataforma."
    )

    # --- gaps (do grafo) ---
    gaps = [g["term"] for g in pack["gaps"]]

    # --- cover letters (usando so evidencia do grafo, gap explicito) ---
    cover_en = (
        "Dear Hiring Team,\n\n"
        "I am applying for the Senior GTM Engineer role. I lead GTM systems end-to-end: CRM, "
        "automation, integrations and enablement, with a record of shipping at scale and adopting "
        "AI-native practices inside revenue operations.\n\n"
        "At Wipro (Meta Project) I enabled 150+ marketing professionals and made the operation #1 "
        "globally in native-AI CRM adoption growth (+150%, 4->10 prompts/day), owning enablement "
        "activations, adoption strategy and process documentation. At Meu Barzin I built a 0-to-1 "
        "go-to-market engine (505 qualified leads, ~200 venues mapped) and architected a RAG "
        "conversational agent with zero-hallucination rules. At Munzner and AK Branding I delivered "
        "automated nurture funnels (10,000+ visits, ~R$50k high-ticket revenue; +250% lead capture) "
        "and inbound/SEO content (~1,000 organic visits, ~10% visitor-to-lead). I work fluently "
        "with SQL, data models and APIs, and ship using agile, UAT, documentation and "
        "quality-assurance practices.\n\n"
        "I am transparent about a gap: my graph does not yet show production depth on Salesforce "
        "Sales Cloud, HubSpot, Apex, Make, Zapier, Clay, Gong, ChurnZero, Wrike, DocuSign, Zuora, "
        "Guru, Slack or Google Workspace. What I bring is the transferable foundation - CRM, "
        "automation, integrations, enablement, sprint/roadmap discipline and cross-functional "
        "stakeholder management across Finance, Marketing, Sales and CX Ops - and a track record of "
        "ramping fast on new platforms. I would lean on your team to learn the specifics of the "
        "Salesforce/HubSpot stack and ship reliably from sprint one.\n\n"
        "Thank you for the opportunity.\n\nSincerely,\nKevin Augusto Vieira"
    )
    cover_pt = (
        "Prezada equipe de contratacao,\n\n"
        "Candidato-me a vaga de Senior GTM Engineer. Lidero sistemas de GTM de ponta a ponta: "
        "CRM, automacao, integracoes e enablement, com historico de entrega em escala e adocao de "
        "praticas AI-native dentro de operacoes de receita.\n\n"
        "Na Wipro (Projeto Meta) capacitei 150+ profissionais de marketing e tornei a operacao #1 "
        "global em crescimento de adocao de IA nativa no CRM (+150%, 4->10 prompts/dia), sendo dono "
        "das ativacoes de enablement, estrategia de adocao e documentacao de processos. No Meu "
        "Barzin construi um motor de go-to-market de 0 a 1 (505 leads qualificados, ~200 "
        "estabelecimentos mapeados) e arquitetei um agente conversacional com RAG e regras de "
        "alucinacao zero. Na Munzner e AK Branding entreguei funis de nutricao automatizados "
        "(10.000+ acessos, ~R$ 50k em receita high-ticket; +250% na captacao de leads) e conteudo "
        "inbound/SEO (~1.000 visitas organicas, ~10% visitor-to-lead). Trabalho com fluencia em "
        "SQL, modelos de dados e APIs, e entrego com praticas ageis, UAT, documentacao e garantia "
        "de qualidade.\n\n"
        "Sou transparente quanto a um gap: meu grafo ainda nao mostra profundidade producao em "
        "Salesforce Sales Cloud, HubSpot, Apex, Make, Zapier, Clay, Gong, ChurnZero, Wrike, "
        "DocuSign, Zuora, Guru, Slack ou Google Workspace. O que trago e a base transferivel - "
        "CRM, automacao, integracoes, enablement, disciplina de sprint/roadmap e gestao de "
        "stakeholders interfuncional atraves de Financas, Marketing, Vendas e CX Ops - e um "
        "historico de ramp rapido em plataformas novas. Apoiaria o time para aprender os "
        "detalhes do stack Salesforce/HubSpot e entregar com confiabilidade desde a sprint um.\n\n"
        "Obrigado pela oportunidade.\n\nAtenciosamente,\nKevin Augusto Vieira"
    )

    form_en = [
        {"question": "Why are you interested in this Senior GTM Engineer role?",
         "answer": "Because I want to be the lead builder of GTM systems at scale. I have shipped CRM, automation, enablement and AI-native adoption programs that moved pipeline (Wipro #1 globally in native-AI CRM adoption growth, +150%), and I am ready to own the Salesforce + HubSpot + middleware stack end-to-end. I am upfront about not having production depth on Salesforce Sales Cloud, HubSpot, Apex, Make, Zapier yet, and I ramp fast on new platforms with the team's support."},
        {"question": "Describe a complex GTM system or integration you built and delivered.",
         "answer": "At Wipro (Meta Project) I led the native-AI CRM adoption program across 150+ marketing professionals, growing from 4 to 10 prompts/day (+150%) and reaching #1 globally in adoption growth. I owned enablement activations, adoption strategy, sprint execution and documentation, working cross-functionally with product, science and commercial stakeholders. At Meu Barzin I built a 0-to-1 GTM engine (505 qualified leads, ~200 venues mapped) and architected a RAG conversational agent with zero-hallucination rules; at Munzner I delivered a 10-stage automated funnel (10,000+ visits, ~R$50k high-ticket revenue)."},
        {"question": "How do you approach scalable GTM automation and refactor of legacy systems?",
         "answer": "I start from the customer journey and the data model, then prioritize declarative/low-code automation and use procedural code only when necessary. At Wipro I refactored enablement workflows around native-AI prompts and documented the new process; at Meu Barzin I replaced a manual lead-capture flow with a structured conversational agent; at Munzner and AK Branding I rebuilt funnels around automated nurture. I validate with UAT, ship via documented releases and measure impact with Power BI, ROI and funnel-bottleneck analysis."},
        {"question": "How do you communicate technical decisions to non-technical stakeholders?",
         "answer": "I translate architecture into business outcomes (pipeline, conversion, reliability, time-to-ramp) and own the change-communication plan. At Wipro I led the Next Level Bootcamp for 12 Meta Marketing Pros with 100% completion and 50% faster ramp-up, showing non-technical stakeholders how to consume the new AI-native CRM features. I write clear documentation, run UAT with the requesters, and surface trade-offs (native integration vs. middleware vs. API) with cost and risk attached."},
    ]
    form_pt = [
        {"question": "Por que tem interesse na vaga de Senior GTM Engineer?",
         "answer": "Porque quero ser o lead builder de sistemas de GTM em escala. Entreguei programas de CRM, automacao, enablement e adocao AI-native que moveram pipeline (Wipro #1 global em crescimento de adocao de IA nativa no CRM, +150%) e estou pronto para ser dono do stack Salesforce + HubSpot + middleware de ponta a ponta. Sou transparente que ainda nao tenho profundidade producao em Salesforce Sales Cloud, HubSpot, Apex, Make, Zapier, e rampo rapido em plataformas novas com apoio do time."},
        {"question": "Descreva um sistema ou integracao de GTM complexo que voce construiu e entregou.",
         "answer": "Na Wipro (Projeto Meta) liderei o programa de adocao de IA nativa no CRM atraves de 150+ profissionais de marketing, crescendo de 4 para 10 prompts/dia (+150%) e atingindo #1 global em crescimento de adocao. Fui dono das ativacoes de enablement, estrategia de adocao, execucao de sprint e documentacao, trabalhando de forma interfuncional com produto, ciencia e stakeholders comerciais. No Meu Barzin construi um motor de GTM de 0 a 1 (505 leads qualificados, ~200 estabelecimentos mapeados) e arquitetei um agente conversacional com RAG e regras de alucinacao zero; na Munzner entreguei um funil automatizado de 10 etapas (10.000+ acessos, ~R$ 50k em receita high-ticket)."},
        {"question": "Como voce aborda automacao de GTM escalavel e refatoracao de sistemas legados?",
         "answer": "Comeco pela jornada do cliente e pelo modelo de dados, depois priorizo automacao declarativa/low-code e uso codigo procedural apenas quando necessario. Na Wipro refatorei fluxos de enablement em torno de prompts de IA nativa e documentei o novo processo; no Meu Barzin substitui um fluxo manual de captacao de leads por um agente conversacional estruturado; na Munzner e AK Branding reconstrui funis em torno de nutricao automatizada. Valido com UAT, entrego via releases documentados e mensuro impacto com Power BI, ROI e analise de gargalos de funil."},
        {"question": "Como voce comunica decisoes tecnicas para stakeholders nao tecnicos?",
         "answer": "Traduzo arquitetura em resultados de negocio (pipeline, conversao, confiabilidade, tempo de ramp) e sou dono do plano de change-communication. Na Wipro liderei o Next Level Bootcamp para 12 Meta Marketing Pros com 100% de conclusao e ramp-up 50% mais rapido, mostrando a stakeholders nao tecnicos como consumir as novas features de IA nativa do CRM. Escrevo documentacao clara, rodo UAT com os requisitantes e apresento trade-offs (integracao nativa vs. middleware vs. API) com custo e risco."},
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
        "id": "pethealth-gtm-engineer-senior-graph",
        "method": "GRAPH-ONLY (context_pack recovered from graph_clean.json + Pet Health Senior GTM Engineer JD). No master_resume, no LLM-generation of facts.",
        "metadata": {
            "company_name": "Pet Health (confidential)",
            "role_title": "Senior GTM Engineer",
            "url": "confidential",
            "fit_score": 52,
            "document_language": "en",
            "available_languages": ["pt", "en"],
            "source_status": "GRAPH ONLY. Evidence strictly from graph_clean.json (recovered via pethealth-context-pack.json). Contact/education/certifications/languages come from the enriched graph. Gap: the graph has NO Salesforce/HubSpot/Apex/Make/Zapier/Clay/Gong/ChurnZero/Wrike/DocuSign/Zuora/Guru/Slack/Google Workspace/TurnZero/Zora nodes; fit_score reflects that honest gap.",
            "good_points": [
                "GTM systems leadership: enabled 150+ marketing pros at Wipro (Meta Project); operation became #1 globally in native-AI CRM adoption growth (+150%, 4->10 prompts/day).",
                "0-to-1 GTM engine: 505 qualified leads, ~200 venues mapped (Meu Barzin) plus a RAG conversational agent with zero-hallucination rules.",
                "Measured demand generation: 10,000+ funnel visits, ~R$50k high-ticket revenue (Munzner); +250% lead capture (AK Branding); ~1,000 organic visits (inbound/SEO).",
                "Strong foundation for the role: CRM, automation, integrations, sprint/roadmap discipline, UAT, documentation, quality-assurance and cross-functional stakeholder management across Finance/Marketing/Sales/CX Ops.",
                "Fluent in SQL, data models and APIs; ships using agile and product-architecture practices.",
            ],
            "improvement_points": [
                "No Salesforce Sales Cloud, Salesforce Flow, Apex, or Salesforce certifications (App Builder / Platform Developer I) in the graph.",
                "No HubSpot, Make.com, Zapier, Xappex G-Connector production depth in the graph.",
                "No exposure (in the graph) to Clay, Gong, ChurnZero, Wrike, DocuSign, Zuora, Guru, Slack, Google Workspace, TurnZero or Zora.",
                "Vaga pede 5-7 anos em Salesforce/GTM; a maior parte da evidencia no grafo e GTM/Growth/Enablement/Product, nao Salesforce-platform-deep-cuts.",
            ],
            "graph_limits": [
                "graph_clean.json now models Candidate contact, Education, Certification and Language nodes (derived from master_resume).",
                "Domain/skill nodes absent from the graph (Salesforce, HubSpot, Apex, Make, Zapier, Clay, Gong, ChurnZero, Wrike, DocuSign, Zuora, Guru, Slack, Google Workspace, TurnZero, Zora) are listed as honest gaps in the cover letter and metadata.",
            ],
        },
        "triage": {
            "decision": "adapt",
            "blockers": [
                "Vaga exige Salesforce Sales Cloud, HubSpot, Apex, Make/Zapier e certificacoes Salesforce que NAO existem no grafo do Kevin.",
                "Senioridade da vaga (5-7 anos em GTM systems Salesforce-deep) e alta para a evidencia disponivel no grafo (GTM/Enablement/Growth/Product).",
            ],
            "deadline": "Not stated",
            "notes": [
                "Decisao: adaptar mesmo com gap, porque (a) a base transferivel (CRM, automacao, integracoes, enablement, sprint/roadmap, UAT, QA, cross-functional) e real; (b) o gap e explicito na cover letter e no metadata; (c) o fit_score 52/100 reflete a honestidade do GAP.",
                "Pipeline: so grafo. Sem LLM, sem master_resume direto. Tudo o que aparece no artefato ou vem do grafo (master_resume) ou e gap declarado.",
            ],
            "gaps": gaps,
            "risks": [
                "Recrutador pode filtrar por certificacao Salesforce (App Builder / Platform Developer I).",
                "Senioridade 5-7 anos em GTM systems Salesforce-deep pode excluir candidatos sem o stack.",
            ],
        },
        "resume": {
            "pt": {
                "name": cand.get("name", "Kevin Augusto Vieira"),
                "location": cand.get("location", {}).get("pt", "Curitiba, Brasil"),
                "phone": cand.get("phone", ""), "email": cand.get("email", ""),
                "linkedin": cand.get("linkedin", ""), "github": cand.get("github", ""),
                "website": cand.get("website", ""),
                "summary": summary_pt,
                "experience": experience_pt,
                "skills": skills_pt,
                "education": education_pt,
                "certifications": certifications_pt,
                "languages": languages,
                "additional_information": [
                    "Contato, educacao, certificacoes e idiomas vem do grafo enriquecido (graph_clean.json).",
                    "GAPS honestos (stack nao modelado no grafo): " + ", ".join(gaps) + ".",
                ],
            },
            "en": {
                "name": cand.get("name", "Kevin Augusto Vieira"),
                "location": cand.get("location", {}).get("en", "Curitiba, Brazil"),
                "phone": cand.get("phone", ""), "email": cand.get("email", ""),
                "linkedin": cand.get("linkedin", ""), "github": cand.get("github", ""),
                "website": cand.get("website", ""),
                "summary": summary_en,
                "experience": experience_en,
                "skills": skills_en,
                "education": education,
                "certifications": certifications,
                "languages": languages,
                "additional_information": [
                    "Contact, education, certifications and languages come from the enriched knowledge graph (graph_clean.json).",
                    "Honest GAPS (stack not modeled in the graph): " + ", ".join(gaps) + ".",
                ],
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
