"""
Career OS — Phase 4: Job Posting Parser & Triple Extraction
Uses Gemini Structured Output to parse job descriptions into structured requirements
and extract triples for the Knowledge Graph.
"""

from __future__ import annotations
import json
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from llm_client import generate_structured
from engine.graph_engine import GraphEngine
from engine.schemas_graph import (
    NodeType, EdgeType, SkillCategory,
    JobPostingNode, RequirementNode, SkillNode, ToolNode,
    create_node, create_edge,
)


# ============================
# PYDANTIC SCHEMAS FOR GEMINI STRUCTURED OUTPUT
# ============================

class ParsedRequirement(BaseModel):
    """A single requirement extracted from job description."""
    description: str = Field(description="Clear, atomic requirement statement")
    category: str = Field(description="Category: technical_skill, soft_skill, tool, experience, education, certification, language, domain_knowledge")
    importance_weight: float = Field(description="Importance 0.0-1.0 (1.0 = must have)", ge=0.0, le=1.0)
    requirement_type: str = Field(description="must_have, nice_to_have, preferred")
    seniority_level: Optional[str] = Field(default=None, description="junior, mid, senior, lead, principal")
    years_experience: Optional[float] = Field(default=None, description="Years of experience required")


class ParsedJobPosting(BaseModel):
    """Complete parsed job posting structure."""
    company_name: str = Field(description="Company name")
    title: str = Field(description="Job title")
    location: str = Field(default="", description="Job location")
    salary_range: str = Field(default="", description="Salary range if mentioned")
    employment_type: str = Field(default="", description="full_time, contract, part_time, internship")
    seniority_level: str = Field(default="senior", description="junior, mid, senior, lead, principal, director")
    summary: str = Field(description="Brief role summary")
    requirements: List[ParsedRequirement] = Field(description="List of all extracted requirements")
    responsibilities: List[str] = Field(default_factory=list, description="Key responsibilities")
    benefits: List[str] = Field(default_factory=list, description="Benefits mentioned")
    tech_stack: List[str] = Field(default_factory=list, description="Technologies/tools mentioned")


class SkillMapping(BaseModel):
    """Maps a requirement to existing skills/tools in our taxonomy."""
    requirement_description: str
    mapped_skills: List[str] = Field(default_factory=list, description="Skill names from taxonomy")
    mapped_tools: List[str] = Field(default_factory=list, description="Tool names from taxonomy")
    confidence: float = Field(description="Mapping confidence 0.0-1.0", ge=0.0, le=1.0)
    reasoning: str = Field(description="Why these skills/tools map to this requirement")


class JobTriples(BaseModel):
    """Complete triple extraction result for KG insertion."""
    job_posting: ParsedJobPosting
    skill_mappings: List[SkillMapping] = Field(description="Requirements mapped to taxonomy skills/tools")
    new_skills: List[str] = Field(default_factory=list, description="Skills not in taxonomy that should be added")
    new_tools: List[str] = Field(default_factory=list, description="Tools not in taxonomy that should be added")


# ============================
# GEMINI PROMPTS
# ============================

JOB_PARSING_PROMPT = """
Você é um especialista em Recrutamento e Análise de Vagas. Sua tarefa é ler a descrição de uma vaga e extrair TODOS os requisitos de forma estruturada e atômica.

REGRAS CRÍTICAS:
1. Cada requisito deve ser ATÔMICO (uma única habilidade/experiência por item)
2. Separe: habilidade técnica, soft skill, ferramenta, experiência, formação, certificação, idioma, conhecimento de domínio
3. Atribua peso de importância (0.0-1.0): 1.0 = obrigatório/must-have, 0.7-0.9 = importante, 0.4-0.6 = desejável, 0.1-0.3 = nice-to-have
4. Classifique tipo: must_have, nice_to_have, preferred
5. Identifique senioridade implícita no requisito
6. NÃO invente requisitos que não estão no texto
7. Inclua tecnologias/ferramentas mencionadas explicitamente

CATEGORIAS VÁLIDAS:
- technical_skill: programação, arquitetura, algoritmos, ML, data, cloud, etc.
- soft_skill: liderança, comunicação, negociação, problem-solving, etc.
- tool: ferramentas específicas (n8n, Salesforce, Figma, Power BI, etc.)
- experience: anos de experiência em domínio/função específica
- education: formação acadêmica (grau, área)
- certification: certificações específicas
- language: idiomas
- domain_knowledge: conhecimento de setor/indústria (fintech, healthtech, e-commerce, etc.)

EXEMPLO DE REQUISITO ATÔMICO:
✅ "5+ anos de experiência em Python para backend"
✅ "Experiência com n8n para automação de workflows"
✅ "Certificação AWS Solutions Architect"
❌ "Experiência em Python, n8n e AWS" (MÚLTIPLOS - separar)

SAÍDA: JSON estruturado conforme schema ParsedJobPosting.
"""

SKILL_MAPPING_PROMPT = """
Você é um especialista em Mapeamento de Competências. Dado:
1. Uma lista de requisitos extraídos de uma vaga
2. Nossa taxonomia de skills e tools (fornecida abaixo)

Sua tarefa: MAPEAR cada requisito para skills/tools EXISTENTES na nossa taxonomia.

REGRAS:
1. Só mapeie para skills/tools que EXISTEM na lista fornecida
2. Se um requisito mappara para múltiplas skills, liste todas
3. Atribua confiança (0.0-1.0): 1.0 = match exato, 0.8 = match forte, 0.6 = match parcial, 0.4 = relacionado
4. Explique o raciocínio do mapeamento
5. Identifique skills/tools NOVOS que não estão na taxonomia (para sugestão de adição)

TAXONOMIA DE SKILLS (categorias principais):
{skill_taxonomy}

TAXONOMIA DE TOOLS:
{tool_taxonomy}

SAÍDA: JSON estruturado conforme schema JobTriples.
"""


# ============================
# JOB POSTING PARSER
# ============================

class JobPostingParser:
    """Parses job descriptions using LLM Structured Output (via OpenRouter, see llm_client.py)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    def parse_from_text(self, job_text: str, company_hint: str = "") -> ParsedJobPosting:
        """Parse job description text into structured requirements."""

        prompt = JOB_PARSING_PROMPT
        if company_hint:
            prompt += f"\n\nDICA: Empresa aparente: {company_hint}"

        prompt += f"\n\nDESCRIÇÃO DA VAGA:\n{job_text}"

        return generate_structured(
            ParsedJobPosting, prompt, temperature=0.1, api_key=self.api_key
        )
    
    def parse_from_url(self, url: str) -> ParsedJobPosting:
        """Fetch and parse job from URL."""
        # This would use the existing fetch_job_description_from_url from utils.py
        # For now, delegate to text parsing
        from utils import fetch_job_description_from_url
        job_text = fetch_job_description_from_url(url)
        # Extract company from URL if possible
        company_hint = self._extract_company_from_url(url)
        return self.parse_from_text(job_text, company_hint)
    
    def _extract_company_from_url(self, url: str) -> str:
        """Extract company name hint from URL."""
        # Simple extraction from common job boards
        if "linkedin.com" in url:
            return "LinkedIn Job"
        elif "gupy.io" in url:
            return "Gupy Job"
        elif "indeed.com" in url:
            return "Indeed Job"
        return ""


# ============================
# TRIPLE EXTRACTION & MAPPING
# ============================

class TripleExtractor:
    """Maps parsed requirements to existing taxonomy skills/tools."""
    
    def __init__(self, graph_engine: GraphEngine, api_key: Optional[str] = None):
        self.engine = graph_engine
        self.api_key = api_key
        self._load_taxonomy()
    
    def _load_taxonomy(self):
        """Load skill and tool names from graph."""
        skills = self.engine.get_nodes_by_type(NodeType.SKILL)
        tools = self.engine.get_nodes_by_type(NodeType.TOOL)
        
        self.skill_names = [s.name for s in skills]
        self.tool_names = [t.name for t in tools]
        
        # Build taxonomy summary for prompt
        self.skill_taxonomy = self._build_taxonomy_summary(self.skill_names)
        self.tool_taxonomy = ", ".join(self.tool_names[:100])  # Limit for token budget
    
    def _build_taxonomy_summary(self, skill_names: List[str]) -> str:
        """Build categorized skill summary for prompt."""
        # Group by category using graph
        categories = {}
        for name in skill_names:
            skill_nodes = [s for s in self.engine.get_nodes_by_type(NodeType.SKILL) if s.name == name]
            if skill_nodes:
                skill = skill_nodes[0]
                cat = skill.category.value
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(name)
        
        lines = []
        for cat, skills in categories.items():
            lines.append(f"{cat}: {', '.join(skills[:30])}")  # Limit per category
        return "\n".join(lines)
    
    def extract_triples(self, parsed_job: ParsedJobPosting) -> JobTriples:
        """Map requirements to taxonomy and identify gaps."""
        
        prompt = SKILL_MAPPING_PROMPT.format(
            skill_taxonomy=self.skill_taxonomy,
            tool_taxonomy=self.tool_taxonomy
        )
        
        prompt += f"\n\nREQUISITOS DA VAGA:\n{json.dumps([r.model_dump() for r in parsed_job.requirements], ensure_ascii=False, indent=2)}"

        return generate_structured(JobTriples, prompt, temperature=0.1, api_key=self.api_key)


# ============================
# GRAPH INSERTION
# ============================

def insert_job_into_graph(
    engine: GraphEngine,
    triples: JobTriples,
    candidate_id: str
) -> Dict[str, Any]:
    """
    Insert parsed job, requirements, and mappings into Knowledge Graph.
    Returns created node IDs for reference.
    """
    job = triples.job_posting
    
    # 1. Create JobPosting node
    job_node = JobPostingNode(
        company_name=job.company_name,
        title=job.title,
        location=job.location,
        salary_range=job.salary_range,
        employment_type=job.employment_type,
        seniority_level=job.seniority_level,
        raw_text=json.dumps(job.model_dump(), ensure_ascii=False),
        status="parsed"
    )
    engine.add_node(job_node)
    job_id = job_node.id
    
    # 2. Link candidate to job (APPLIED_TO)
    engine.add_edge(create_edge(EdgeType.APPLIED_TO, candidate_id, job_id))
    
    # 3. Create Requirement nodes and map to skills/tools
    requirement_ids = []
    skill_mapping_ids = []
    
    for i, req in enumerate(job.requirements):
        req_node = RequirementNode(
            description=req.description,
            importance_weight=req.importance_weight,
            requirement_type=req.requirement_type,
            category=req.category
        )
        engine.add_node(req_node)
        requirement_ids.append(req_node.id)
        
        # Job -> REQUIRES -> Requirement
        engine.add_edge(create_edge(EdgeType.REQUIRES, job_id, req_node.id))
        
        # Find corresponding skill mapping
        mapping = None
        for m in triples.skill_mappings:
            if m.requirement_description == req.description:
                mapping = m
                break
        
        if mapping:
            # Map to skills
            for skill_name in mapping.mapped_skills:
                skill_nodes = [s for s in engine.get_nodes_by_type(NodeType.SKILL) if s.name == skill_name]
                if skill_nodes:
                    skill_id = skill_nodes[0].id
                    # Requirement -> MAPS_TO_SKILL -> Skill
                    engine.add_edge(create_edge(EdgeType.MAPS_TO_SKILL, req_node.id, skill_id))
            
            # Map to tools
            for tool_name in mapping.mapped_tools:
                tool_nodes = [t for t in engine.get_nodes_by_type(NodeType.TOOL) if t.name == tool_name]
                if tool_nodes:
                    tool_id = tool_nodes[0].id
                    # Requirement -> MAPS_TO_TOOL -> Tool
                    engine.add_edge(create_edge(EdgeType.MAPS_TO_TOOL, req_node.id, tool_id))
    
    # 4. Track new skills/tools to add to taxonomy
    new_skills_added = []
    for skill_name in triples.new_skills:
        # Check if already exists
        existing = [s for s in engine.get_nodes_by_type(NodeType.SKILL) if s.name == skill_name]
        if not existing:
            new_skill = SkillNode(
                name=skill_name,
                category=SkillCategory.TECHNICAL,  # Default, will be refined
                level=3,
                description_pt=skill_name,
                description_en=skill_name,
                years_experience=0.0
            )
            engine.add_node(new_skill)
            new_skills_added.append(skill_name)
    
    new_tools_added = []
    for tool_name in triples.new_tools:
        existing = [t for t in engine.get_nodes_by_type(NodeType.TOOL) if t.name == tool_name]
        if not existing:
            new_tool = ToolNode(
                name=tool_name,
                vendor="",
                tool_type="Other",
                proficiency=3,
                description_pt=tool_name,
                description_en=tool_name
            )
            engine.add_node(new_tool)
            new_tools_added.append(tool_name)
    
    return {
        "job_id": job_id,
        "requirement_ids": requirement_ids,
        "new_skills_added": new_skills_added,
        "new_tools_added": new_tools_added,
        "total_requirements": len(requirement_ids),
        "mapped_requirements": len([m for m in triples.skill_mappings if m.mapped_skills or m.mapped_tools])
    }


# ============================
# MAIN PIPELINE
# ============================

class JobProcessingPipeline:
    """End-to-end pipeline: Job Text → Parsed → Mapped → Graph."""
    
    def __init__(self, graph_engine: GraphEngine, api_key: Optional[str] = None):
        self.engine = graph_engine
        self.parser = JobPostingParser(api_key)
        self.extractor = TripleExtractor(graph_engine, api_key)
    
    def process_job_text(self, job_text: str, company_hint: str = "") -> Dict[str, Any]:
        """Process job text through full pipeline."""
        
        print(f"[1/3] Parsing job description...")
        parsed_job = self.parser.parse_from_text(job_text, company_hint)
        print(f"  Parsed: {parsed_job.company_name} - {parsed_job.title}")
        print(f"  Requirements: {len(parsed_job.requirements)}")
        
        print(f"[2/3] Extracting triples & mapping to taxonomy...")
        triples = self.extractor.extract_triples(parsed_job)
        print(f"  Skill mappings: {len([m for m in triples.skill_mappings if m.mapped_skills])}")
        print(f"  Tool mappings: {len([m for m in triples.skill_mappings if m.mapped_tools])}")
        print(f"  New skills suggested: {len(triples.new_skills)}")
        print(f"  New tools suggested: {len(triples.new_tools)}")
        
        # Find candidate
        candidates = self.engine.get_nodes_by_type(NodeType.CANDIDATE)
        if not candidates:
            raise ValueError("No candidate found in graph")
        candidate_id = candidates[0].id
        
        print(f"[3/3] Inserting into Knowledge Graph...")
        result = insert_job_into_graph(self.engine, triples, candidate_id)
        print(f"  Job node: {result['job_id']}")
        print(f"  Requirements: {result['total_requirements']}")
        print(f"  Mapped: {result['mapped_requirements']}")
        print(f"  New skills: {result['new_skills_added']}")
        print(f"  New tools: {result['new_tools_added']}")
        
        return {
            "parsed_job": parsed_job,
            "triples": triples,
            "graph_result": result
        }
    
    def process_job_url(self, url: str) -> Dict[str, Any]:
        """Process job from URL."""
        print(f"[1/3] Fetching job from URL...")
        from utils import fetch_job_description_from_url
        job_text = fetch_job_description_from_url(url)
        company_hint = self.parser._extract_company_from_url(url)
        return self.process_job_text(job_text, company_hint)


if __name__ == "__main__":
    # Test with sample job description
    sample_job = """
    Vaga: Senior Product Manager - AI Products
    Empresa: TechCorp Brasil
    Local: São Paulo, SP (Híbrido)
    Salário: R$ 18.000 - R$ 25.000
    
    Sobre a vaga:
    Buscamos um Senior Product Manager para liderar nossa linha de produtos baseados em IA.
    Você será responsável pela estratégia de produto, discovery, roadmap e delivery de features
    que utilizam LLMs, RAG e agentes autônomos.
    
    Requisitos Obrigatórios:
    - 5+ anos de experiência em Product Management
    - Experiência comprovada com produtos de IA/ML (LLMs, RAG, embeddings)
    - Sólido background técnico (CS, Engenharia ou equivalente)
    - Experiência com Python, APIs REST, bancos de dados vetoriais (Pinecone, Weaviate)
    - Experiência com ferramentas de orquestração (n8n, LangChain, LangGraph)
    - Metodologias ágeis (Scrum, Kanban) e frameworks de discovery (Jobs-to-be-Done, Opportunity Solution Tree)
    - Inglês avançado (technical fluency)
    
    Desejáveis:
    - Experiência com fine-tuning de LLMs (LoRA, QLoRA)
    - Conhecimento de MLOps e observabilidade de modelos
    - Experiência em produtos B2B SaaS
    - Certificação em Product Management (Pragmatic, Reforge, etc.)
    
    Responsabilidades:
    - Definir visão e estratégia de produtos de IA
    - Conduzir discovery contínuo com usuários e stakeholders
    - Priorizar roadmap usando frameworks baseados em outcomes
    - Trabalhar próximo a engenharia de ML e dados
    - Medir sucesso via métricas de adoção, qualidade e ROI
    """
    
    # Note: Requires API key to run
    print("Sample job ready for processing. Set OPENROUTER_API_KEY to run.")
    print(f"Sample text length: {len(sample_job)} chars")