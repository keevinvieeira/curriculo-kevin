import os
import json
import requests
from io import BytesIO
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from jinja2 import Template
from bs4 import BeautifulSoup
from dotenv import load_dotenv

try:
    from xhtml2pdf import pisa
except Exception:
    pisa = None

from llm_client import generate_structured

# Load environment variables
load_dotenv()

SECTION_TITLES = {
    "pt": {
        "summary": "Resumo Profissional",
        "experience": "Experiência Profissional",
        "skills": "Habilidades",
        "education": "Education",
        "certifications": "Certificações",
        "languages": "Idiomas",
        "additional_info": "Informações Adicionais"
    },
    "en": {
        "summary": "Professional Summary",
        "experience": "Professional Experience",
        "skills": "Skills",
        "education": "Education",
        "certifications": "Certifications",
        "languages": "Languages",
        "additional_info": "Additional Information"
    }
}

# Schema for Structured Output - Adapted Resume
class ExperienceItem(BaseModel):
    company: str
    role: str
    dates: str
    location: Optional[str] = None
    bullets: List[str] = Field(description="List of bullet points summarizing achievements and responsibilities tailored to the job description.")

class SkillCategory(BaseModel):
    category: str
    skills: List[str] = Field(description="Relevant technical or soft skills in this category.")

class EducationItem(BaseModel):
    institution: str
    degree: str
    dates: str

class CertificationItem(BaseModel):
    name: str
    issuer: str
    status: str

class LanguageItem(BaseModel):
    language: str
    proficiency: str

class AdaptedResume(BaseModel):
    name: str
    location: str
    phone: str
    email: str
    linkedin: str
    github: Optional[str] = ""
    website: Optional[str] = ""
    summary: str = Field(description="A highly tailored professional summary focusing on how the candidate's background matches the target role.")
    experience: List[ExperienceItem] = Field(description="Adapted list of professional experiences.")
    skills: List[SkillCategory] = Field(description="Grouped skills relevant to the target role.")
    education: List[EducationItem] = Field(description="Academic education history.")
    certifications: List[CertificationItem] = Field(description="Relevant certifications.")
    languages: List[LanguageItem] = Field(description="Language proficiencies.")
    additional_information: Optional[List[str]] = Field(default=None, description="Other relevant info, e.g. industry contexts or portfolios.")

# Schema for Job Materials (Cover Letter and Form Answers)
class FormAnswer(BaseModel):
    question: str = Field(description="A common job application form question (e.g. why this company, project management style, etc.)")
    answer: str = Field(description="A highly customized, persuasive, and professional response using Kevin's real experiences.")

class JobMaterials(BaseModel):
    cover_letter: str = Field(description="A tailored, professional cover letter for the role.")
    form_answers: List[FormAnswer] = Field(description="A list of helpful prepared responses for common application form questions.")

def load_master_resume(filepath: str = "master_resume.json") -> Dict[str, Any]:
    """Load the master resume JSON database."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Master resume database not found at {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_master_resume(data: Dict[str, Any], filepath: str = "master_resume.json"):
    """Save updates back to the master resume JSON database."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_job_description_from_url(url: str) -> str:
    """Fetch and extract clean text content from a job posting URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        for element in soup(["script", "style", "header", "footer", "nav", "aside", "noscript", "svg"]):
            element.decompose()
            
        text = soup.get_text(separator=" ")
        
        lines = []
        for line in text.splitlines():
            cleaned_line = " ".join(line.split()).strip()
            if cleaned_line:
                lines.append(cleaned_line)
                
        cleaned_text = "\n".join(lines)
        
        if len(cleaned_text.strip()) < 100:
            raise ValueError("O conteúdo extraído da página é muito curto. O site pode estar bloqueando a leitura automatizada.")
            
        return cleaned_text
    except Exception as e:
        raise ValueError(f"Erro ao acessar a URL: {str(e)}. Tente copiar e colar a descrição manualmente.")

def adapt_resume_with_llm(
    master_resume: Dict[str, Any],
    job_description: str,
    target_lang: str,
    api_key: Optional[str] = None
) -> AdaptedResume:
    """Use an LLM (via OpenRouter) to adapt the master resume to the job description.

    Renamed from adapt_resume_with_gemini() when the project moved off a direct Gemini
    dependency onto OpenRouter (see llm_client.py). No other module called the old name,
    so this rename is safe.
    """
    lang_name = "Português" if target_lang.lower() in ["pt", "português", "portugues"] else "English"
    
    prompt = f"""
    Você é um especialista em Recrutamento, Seleção e Personalização de Currículos de alto nível.
    Sua missão é ler a Descrição da Vaga (Job Description) abaixo e adaptar o Currículo Mestre do Kevin Augusto Vieira para esta vaga.
    
    O idioma final do currículo adaptado deve ser: {lang_name} (se for 'English', use termos profissionais americanos; se for 'Português', use português corporativo formal do Brasil).
    
    ### DIRETRIZES DE ADAPTAÇÃO:
    1. **Dados Pessoais:** Use as informações do currículo mestre diretamente.
    2. **Resumo Profissional:** Reescreva um resumo profissional poderoso (em {lang_name}) com cerca de 150-200 palavras. Conecte diretamente as maiores forças de Kevin (ex: mais de 8 anos de experiência em marketing/produto, liderança de bootcamps na Wipro/Meta, fundação de startup baseada em IA, automações n8n/Supabase, metodologia Thinking Environment) com os requisitos essenciais da vaga.
    3. **Experiência Profissional:**
       - Filtre e selecione as experiências mais marcantes. Priorize Wipro, Meu Barzin, AK Branding e Munzner.
       - Selecione e reescreva os bullet points das experiências (do currículo mestre) para usar verbos de ação fortes e palavras-chave que correspondam aos requisitos da vaga.
       - Se a vaga for muito focada em Gestão de Projetos ou Operações, use os bullet points orientados a PMO e processos (ex: Wipro Bootcamp, CRM integration Munzner, Supabase Meu Barzin). Se for focada em Growth/Marketing, use os bullets focados em canais, aquisição, campanhas de ads, branding.
       - NUNCA invente conquistas, empresas, cargos ou datas. Apenas reescreva e selecione as informações reais do currículo mestre para destacar o que é mais relevante para o recrutador dessa vaga.
    4. **Competências (Technical Skills):** Agrupe e selecione apenas as competências do currículo mestre que façam sentido para a vaga. Traduza-as para o idioma {lang_name} de forma precisa.
    5. **Certificações, Formação e Idiomas:** Selecione e traduza conforme o idioma solicitado.
    
    ### DADOS DE ENTRADA:
    ---
    CURRÍCULO MESTRE (JSON):
    {json.dumps(master_resume, ensure_ascii=False, indent=2)}
    ---
    DESCRIÇÃO DA VAGA (JOB DESCRIPTION):
    {job_description}
    ---
    
    Gere a resposta estruturada contendo o currículo adaptado completo em {lang_name}.
    """

    return generate_structured(AdaptedResume, prompt, temperature=0.2, api_key=api_key)

def generate_job_materials(
    master_resume: Dict[str, Any],
    job_description: str,
    target_lang: str,
    api_key: Optional[str] = None
) -> JobMaterials:
    """Use an LLM (via OpenRouter) to generate a cover letter and form answers matching the job description."""
    lang_name = "Português" if target_lang.lower() in ["pt", "português", "portugues"] else "English"
    
    prompt = f"""
    Você é um Coach de Carreira e Redator Profissional.
    Com base no Currículo Mestre do Kevin Augusto Vieira e na Descrição da Vaga abaixo, gere materiais de candidatura em {lang_name}:
    
    1. **Carta de Apresentação (Cover Letter):** Uma carta persuasiva, calorosa, profissional e focada em resultados (cerca de 250-350 palavras). Ela deve explicar por que o Kevin é o candidato ideal para a vaga, destacando suas conquistas marcantes (ex: atuação no Projeto Libra da Meta via Wipro, arquitetura de IA e UX na startup Meu Barzin, ou sua experiência robusta de 6 anos na Munzner).
    2. **Perguntas de Formulários (Form Answers):** Crie respostas para pelo menos 3 perguntas comuns em processos seletivos (ex: 'Fale sobre um desafio técnico ou de processos e como resolveu', 'Qual sua experiência com CRM/Marketing Automation', 'Por que você quer trabalhar conosco?', ou 'Como você lidera equipes de alta performance'). As respostas devem ser realistas e usar os fatos reais do Kevin (ex: automação n8n/Supabase, facilitação com Thinking Environment, ou dashboards Power BI).
    
    ### DADOS DE ENTRADA:
    ---
    CURRÍCULO MESTRE:
    {json.dumps(master_resume, ensure_ascii=False, indent=2)}
    ---
    DESCRIÇÃO DA VAGA (JOB DESCRIPTION):
    {job_description}
    ---
    
    Gere a resposta estruturada contendo a carta de apresentação e as respostas para formulários em {lang_name}.
    """

    return generate_structured(JobMaterials, prompt, temperature=0.3, api_key=api_key)

def render_html_resume(adapted_resume: AdaptedResume, target_lang: str = "pt", template_path: str = "templates/resume_theme.html") -> str:
    """Render the adapted resume data into the HTML template."""
    with open(template_path, "r", encoding="utf-8") as f:
        template_content = f.read()
    
    lang_code = "en" if target_lang.lower() in ["en", "english", "inglês", "ingles"] else "pt"
    titles = SECTION_TITLES[lang_code]
    
    template = Template(template_content)
    resume_data = adapted_resume.model_dump()
    resume_data["titles"] = titles
    return template.render(**resume_data)

def render_html_cover_letter(cover_letter_text: str) -> str:
    """Render cover letter text into a clean HTML document for PDF conversion."""
    paragraphs = cover_letter_text.strip().split("\n\n")
    formatted_paragraphs = "".join([f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip()])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: A4;
            margin: 2cm 2.5cm;
        }}
        body {{
            font-family: Helvetica, Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.65;
            color: #222222;
        }}
        p {{
            margin-bottom: 14pt;
            text-align: justify;
        }}
    </style>
</head>
<body>
    {formatted_paragraphs}
</body>
</html>"""
    return html

def convert_html_to_pdf(html_content: str) -> bytes:
    """Convert HTML content to PDF bytes using xhtml2pdf."""
    if pisa is None:
        raise RuntimeError("xhtml2pdf não está disponível neste ambiente.")
    pdf_buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        raise RuntimeError("Erro ao gerar o arquivo PDF a partir do HTML.")
    return pdf_buffer.getvalue()

def convert_resume_to_markdown(adapted_resume: AdaptedResume, target_lang: str = "pt") -> str:
    """Convert AdaptedResume data to a clean Markdown representation."""
    r = adapted_resume
    lang_code = "en" if target_lang.lower() in ["en", "english", "inglês", "ingles"] else "pt"
    t = SECTION_TITLES[lang_code]
    md = []
    
    md.append(f"# {r.name}")
    contact_parts = []
    if r.location: contact_parts.append(f"📍 {r.location}")
    if r.phone: contact_parts.append(f"📞 {r.phone}")
    if r.email: contact_parts.append(f"✉️ {r.email}")
    if r.linkedin: contact_parts.append(f"🔗 {r.linkedin}")
    if r.github: contact_parts.append(f"💻 {r.github}")
    if r.website: contact_parts.append(f"🌐 {r.website}")
    md.append(" | ".join(contact_parts))
    md.append("\n---\n")
    
    md.append(f"## {t['summary']}")
    md.append(r.summary)
    md.append("")
    
    md.append(f"## {t['experience']}")
    for exp in r.experience:
        header = f"### {exp.role} | {exp.company}"
        md.append(header)
        md.append(f"*{exp.dates}*")
        if exp.location:
            md.append(f"*{exp.location}*")
        md.append("")
        for bullet in exp.bullets:
            md.append(f"- {bullet}")
        md.append("")
        
    md.append(f"## {t['skills']}")
    for cat in r.skills:
        skills_str = ", ".join(cat.skills)
        md.append(f"- **{cat.category}**: {skills_str}")
    md.append("")
    
    md.append(f"## {t['education']}")
    for edu in r.education:
        md.append(f"- **{edu.degree}** — {edu.institution} ({edu.dates})")
    md.append("")
    
    md.append(f"## {t['certifications']}")
    for cert in r.certifications:
        md.append(f"- **{cert.name}** — {cert.issuer} ({cert.status})")
    md.append("")
    
    md.append(f"## {t['languages']}")
    for lang in r.languages:
        md.append(f"- **{lang.language}**: {lang.proficiency}")
    md.append("")
    
    if r.additional_information:
        md.append(f"## {t['additional_info']}")
        for info in r.additional_information:
            md.append(info)
        md.append("")
        
    return "\n".join(md)

def build_generic_adapted_resume(master_resume: Dict[str, Any], target_lang: str = "pt") -> AdaptedResume:
    """Build a comprehensive generic AdaptedResume object directly from the master resume JSON."""
    lang_code = "en" if target_lang.lower() in ["en", "english", "inglês", "ingles"] else "pt"
    
    p = master_resume.get("personal_info", {})
    name = p.get("name", "Kevin Augusto Vieira")
    loc = p.get("location", {}).get(lang_code, "Curitiba, PR")
    phone = p.get("phone", "")
    email = p.get("email", "")
    linkedin = p.get("linkedin", "")
    github = p.get("github", "")
    website = p.get("website", "")
    
    # Summary
    summaries = master_resume.get("professional_summaries", [])
    summary_text = summaries[0].get("content", {}).get(lang_code, "") if summaries else ""
    
    # Experiences
    experiences: List[ExperienceItem] = []
    for comp in master_resume.get("work_experience", []):
        company = comp.get("company", "")
        roles = comp.get("roles", [])
        role_title = roles[0].get("title", {}).get(lang_code, "") if roles else ""
        dates = roles[0].get("dates", {}).get(lang_code, "") if roles else ""
        location = comp.get("location", {}).get(lang_code, "") if comp.get("location") else None
        
        bullets: List[str] = []
        for b in comp.get("bullets", []):
            text = b.get(lang_code, "")
            if text:
                bullets.append(text)
        
        # Take top 2 bullets for concise 1-page fit across all 5 experiences
        bullets = bullets[:2] if len(bullets) > 2 else bullets
                
        if company and role_title and bullets:
            experiences.append(ExperienceItem(
                company=company,
                role=role_title,
                dates=dates,
                location=location,
                bullets=bullets
            ))
            
    # Technical Skills
    skills_data = master_resume.get("technical_skills", {}).get(lang_code, [])
    skills: List[SkillCategory] = []
    for item in skills_data:
        skills.append(SkillCategory(
            category=item.get("category", ""),
            skills=item.get("skills", [])
        ))
        
    # Education
    education: List[EducationItem] = []
    for edu in master_resume.get("education", []):
        institution = edu.get("institution", "")
        degree_dict = edu.get("degree", {})
        degree = degree_dict.get(lang_code, degree_dict.get("pt", "")) if isinstance(degree_dict, dict) else str(degree_dict)
        dates = edu.get("dates", "")
        education.append(EducationItem(
            institution=institution,
            degree=degree,
            dates=dates
        ))
        
    # Certifications
    certifications: List[CertificationItem] = []
    for cert in master_resume.get("certifications", []):
        name_cert = cert.get("name", "")
        issuer = cert.get("issuer", "")
        status_dict = cert.get("status", {})
        status = status_dict.get(lang_code, status_dict.get("pt", "")) if isinstance(status_dict, dict) else str(status_dict)
        certifications.append(CertificationItem(
            name=name_cert,
            issuer=issuer,
            status=status
        ))
        
    # Languages
    languages_data = master_resume.get("languages", {}).get(lang_code, [])
    languages: List[LanguageItem] = []
    for lang_item in languages_data:
        languages.append(LanguageItem(
            language=lang_item.get("language", ""),
            proficiency=lang_item.get("proficiency", "")
        ))
        
    # Additional Information (Grouped for concise 1-page fit)
    if lang_code == "pt":
        additional_info = [
            "Esporte & Wellness: Faixa-Roxa de Jiu-Jitsu (BJJ), praticante de Yoga e Mindfulness, com foco em saúde integrativa, longevidade e soluções para o mercado de bem-estar (HealthTech).",
            "Formação Humana: Especialista em Filosofia Clínica com foco em inteligência emocional e autoconhecimento aplicado a dinâmicas de facilitação humana corporativa."
        ]
    else:
        additional_info = [
            "Sports & Wellness: BJJ Purple Belt (Brazilian Jiu-Jitsu), dedicated Yoga and Mindfulness practitioner, focused on integrative health, longevity, and HealthTech solutions.",
            "Human Facilitation: Specialist in Clinical Philosophy with a focus on emotional intelligence and self-awareness applied to corporate human facilitation and leadership dynamics."
        ]
    
    return AdaptedResume(
        name=name,
        location=loc,
        phone=phone,
        email=email,
        linkedin=linkedin,
        github=github,
        website=website,
        summary=summary_text,
        experience=experiences,
        skills=skills,
        education=education,
        certifications=certifications,
        languages=languages,
        additional_information=additional_info
    )

