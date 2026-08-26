# Career OS — Pipeline de Adaptação de Currículo (Documentação)

Este repositório implementa o **Career OS**: um sistema pessoal onde o
`master_resume.json` é a **fonte única de verdade** (PT/EN) e cada vaga vira um
**artefato versionado** (`data/jobs/<slug>.json`) que o app Streamlit consome para
pré-visualizar, exportar em PDF/Markdown e registrar no painel de candidaturas.

Princípio central: **zero alucinação**. Nenhuma experiência, empresa, cargo, ferramenta,
métrica ou resultado pode ser inventado. A adaptação muda ênfase e linguagem, nunca os
fatos. Toda skill declarada no artefato precisa existir literalmente no `master_resume.json`.

---

## 1. Arquitetura

```
master_resume.json          <- FONTE ÚNICA DE VERDADE (PT/EN)
        │
        │  (vaga: URL ou texto colado)
        ▼
utils.fetch_job_description_from_url(url)   <- extrai texto da JD (BeautifulSoup)
        │
        ▼
utils.adapt_resume_with_gemini(...)          <- GERA AdaptedResume (PT e EN)  [LLM]
utils.generate_job_materials(...)            <- GERA carta + respostas (PT e EN) [LLM]
        │
        ▼
job_store.create_from_active(job_id)         <- empacota em data/jobs/<slug>.json
        │
        ▼
job_store.validate_job(job, master)          <- VALIDAÇÃO DETERMINÍSTICA anti-alucinação
        │
        ▼
job_store.activate_job(job_id, master)       <- grava data/active.json + arquivos do app
        │
        ▼
streamlit run app.py                         <- Visualizar / exportar / registrar
```

Módulos:
- `utils.py` — schema Pydantic (`AdaptedResume`, `JobMaterials`), parsing da JD,
  adaptação via LLM, render HTML→PDF, markdown.
- `engine/job_parser.py` — `JobProcessingPipeline`: parsing estruturado da JD em
  requisitos + mapeamento para a taxonomia do grafo (caminho do Knowledge Graph; não
  escreve o artefato de adaptação, serve para o grafo/insights).
- `job_store.py` — empacotamento, validação e ativação de artefatos.
- `app.py` — Streamlit (4 abas: Estúdio, Painel, Visualizador Neural, Editor Mestre).
- `scripts/export_adapted_resumes.py` — gera PDFs de lote.
- `scripts/register_shortlist_applications.py` — registra vagas em `applications.json`.

---

## 2. Pipeline passo a passo (como qualquer IA deve executar)

### Passo A — Obter a descrição da vaga (JD)
- Se a URL for acessível: `utils.fetch_job_description_from_url(url)` (remove
  script/style/nav e devolve texto puro).
- Se o site bloquear (Ashby/SPA, login, 401): **não inventar**. Pedir ao usuário o
  texto da vaga colado, ou buscar fontes espelho confiáveis (Getro, Teal, HireConcierge)
  que republiquem o posting do Ashby. Registrar a origem em `metadata.source_status`.

### Passo B — Gerar a adaptação (LLM)
- `utils.adapt_resume_with_gemini(master_resume, job_description, "pt")` → `AdaptedResume`
- `utils.adapt_resume_with_gemini(master_resume, job_description, "en")` → `AdaptedResume`
- Regras do prompt (já codificadas): nunca inventar; selecionar/reescrever apenas fatos
  reais do master; temperatura 0.2.
- Nota de implementação: o projeto original usa Gemini. Se a `GEMINI_API_KEY` não
  estiver disponível, a adaptação pode ser produzida por outro modelo, desde que o
  **conteúdo** obedeça às mesmas regras e o **schema** de saída seja idêntico.

### Passo C — Gerar materiais (LLM)
- `utils.generate_job_materials(master_resume, job_description, "pt")` → `JobMaterials`
- `utils.generate_job_materials(master_resume, job_description, "en")` → `JobMaterials`

### Passo D — Empacotar o artefato
Estrutura de `data/jobs/<slug>.json` (ver exemplo em `data/jobs/modaxo-ai-transformation-manager.json`):

```json
{
  "id": "<slug>",
  "metadata": {
    "company_name": "...", "role_title": "...", "url": "...",
    "fit_score": <int 0-100>, "document_language": "en|pt",
    "available_languages": ["pt","en"],
    "location": "...", "work_model": "...", "employment_type": "...",
    "salary_range": "...", "salary_expectation": "...",
    "source_files": ["master_resume.json"],
    "good_points": [...], "improvement_points": [...]
  },
  "triage": {
    "decision": "adapt|hold|discard",
    "notes": [...], "gaps": [...], "risks": [...]
  },
  "resume":  { "pt": {<AdaptedResume>}, "en": {<AdaptedResume>} },
  "materials": { "pt": {<JobMaterials>}, "en": {<JobMaterials>} },
  "evidence": { "skills": { "pt": [...], "en": [...] } }
}
```

`evidence.skills` deve listar **apenas** skills que existem literalmente em
`master_resume.json` (casefold) — é o que `validate_job` checa.

### Passo E — Validar (obrigatório, determinístico)
`job_store.validate_job(job, master_resume)` falha se:
1. faltar `metadata.company_name` ou `role_title`;
2. faltar `resume`/`materials` em pt e en;
3. `triage.decision` ≠ adapt|hold|discard;
4. faltar `summary` no resume;
5. houver título proibido (founder/co-founder) no resume;
6. a carta não citar a empresa-alvo;
7. alguma skill em `evidence.skills` não existir no master.

### Passo F — Ativar no Streamlit
`python -m scripts.activate_job <slug> --validate`
- grava `data/active.json` (ponteiro),
- escreve `metadata.json`, `adapted_resume_pt.json`, `adapted_resume_en.json`,
  `job_materials_pt.json`, `job_materials_en.json`,
- copia a versão padrão (`document_language`) para `adapted_resume.json`/`job_materials.json`.

### Passo G — Visualizar
`streamlit run app.py` → aba **Estúdio de Adaptação** mostra o currículo ativo;
botão "Registrar no Painel" adiciona a `applications.json`.

---

## 3. Como adaptar esta vaga específica (exemplo reproduzível)

Para a vaga SandboxAQ "Product & Growth Marketer, AI Simulation" (ashby_jid
42615b29-0fcb-429c-b305-8fa6b1137153):
1. JD obtida via fontes espelho (Ashby bloqueou a API; landing page é SPA).
2. Gerar PT+EN com as regras de zero-hallucination.
3. `evidence.skills` = subset do master (ex: Product Marketing, GTM, Inbound/SEO,
   CRM & Automation, Sales Enablement, AI native implementation, n8n, Power BI).
4. `improvement_points` honestos: sem exposição direta a life sciences/chemistry/
   biopharma; inglês avançado/profissional (não "fluent"); profundidade técnica de
   LLM/LQM não documentada.

---

## 4. Regras de ouro (não violáveis)
1. master_resume.json é imutável como fonte; a adaptação só reescreve/selectiona.
2. Nunca criar empresa, cargo, métrica ou ferramenta inexistente no master.
3. Competência transferível = apresentada como transferível, não como experiência direta.
4. Lacunas relevantes vão para `improvement_points` e para as respostas de formulário.
5. Sempre validar (`validate_job`) antes de ativar.
6. Sempre versionar o artefato em `data/jobs/` (nunca editar só os arquivos ativos).
