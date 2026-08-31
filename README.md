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
utils.adapt_resume_with_llm(...)             <- GERA AdaptedResume (PT e EN)  [LLM via OpenRouter]
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
- `app.py` — Streamlit (5 abas: Estúdio, Fila de Aprovação, Painel, Visualizador
  Neural, Editor Mestre).
- `scripts/export_adapted_resumes.py` — gera PDFs de lote.
- `scripts/register_shortlist_applications.py` — registra vagas em `applications.json`.
- `engine/automation/`, `engine/application/`, `scripts/run_automation_cycle.py`,
  `scripts/run_application_agent.py`, `scripts/run_submit_agent.py` — camada de
  automação (radar → fila de aprovação → Application Prep Agent → gate de envio),
  ver seção 5 abaixo.

---

## 2. Pipeline passo a passo (como qualquer IA deve executar)

### Passo A — Obter a descrição da vaga (JD)
- Se a URL for acessível: `utils.fetch_job_description_from_url(url)` (remove
  script/style/nav e devolve texto puro).
- Se o site bloquear (Ashby/SPA, login, 401): **não inventar**. Pedir ao usuário o
  texto da vaga colado, ou buscar fontes espelho confiáveis (Getro, Teal, HireConcierge)
  que republiquem o posting do Ashby. Registrar a origem em `metadata.source_status`.

### Passo B — Gerar a adaptação (LLM)
- `utils.adapt_resume_with_llm(master_resume, job_description, "pt")` → `AdaptedResume`
- `utils.adapt_resume_with_llm(master_resume, job_description, "en")` → `AdaptedResume`
- Regras do prompt (já codificadas): nunca inventar; selecionar/reescrever apenas fatos
  reais do master; temperatura 0.2.
- Nota de implementação: o backend de LLM é a OpenRouter (`llm_client.py`, via
  `instructor`), configurável por `OPENROUTER_API_KEY`/`OPENROUTER_MODEL` no `.env`
  (ver `.env.example`) — trocar de modelo é só mudar essa variável, sem tocar em
  código. O projeto usava Gemini diretamente antes da migração; qualquer modelo
  configurado deve obedecer às mesmas regras de conteúdo e ao mesmo **schema**
  Pydantic de saída.

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

---

## 5. Automação (radar → adaptação → aprovação → candidatura)

Camada opcional, construída em cima do pipeline acima sem reescrever nada dele —
tudo aqui *reaproveita* `job_store`/`JobPipeline`/`utils.adapt_resume_with_llm` e
adiciona descoberta de vagas, um `fit_score` determinístico e dois gates humanos
estruturais antes de qualquer candidatura real ser enviada.

### 5.1 Estados (`engine/automation/state_machine.py`)

```
DISCOVERED → QUALIFIED → ADAPTING → VALIDATING → AWAITING_RESUME_APPROVAL
    → RESUME_APPROVED → APPLICATION_PREPARING → AWAITING_APPLICATION_REVIEW
    → READY_TO_SUBMIT → SUBMIT_APPROVED → APPLIED
```
mais os estados laterais `HOLD` / `DISCARDED` / `EXPIRED` / `BLOCKED` / `FAILED`.
As transições válidas são uma tabela explícita (`TRANSITIONS`) — nunca inferidas por
quais arquivos existem em disco — e um job sem bloco `automation` (todo job criado
antes desta camada existir, ou criado manualmente) simplesmente fica fora da máquina
de estados, sem exigir nenhuma mudança em `validate_job`.

**Os dois gates humanos do plano original são transições específicas, e nenhum
código consegue pular nenhuma delas:**
- **Gate #1 — Aprovar currículo:** `AWAITING_RESUME_APPROVAL → RESUME_APPROVED`
  (botão "✅ Aprovar currículo" na aba Fila de Aprovação do Streamlit).
- **Gate #2 — Aprovar envio:** `READY_TO_SUBMIT → SUBMIT_APPROVED` (botão
  "🚀 Aprovar envio" na mesma aba). Só depois desse estado
  `engine/application/submit.py` tem permissão de clicar em qualquer botão de envio
  real — e mesmo assim só registra `APPLIED` se detectar um indicador real de
  sucesso na página resultante.

### 5.2 Peças

| Módulo | O que faz |
|---|---|
| `engine/automation/radar.py` | Descobre vagas em boards públicos (Greenhouse/Lever/Ashby — LinkedIn e Gupy ficam de fora, ToS). |
| `engine/automation/dedupe.py` | URL normalizada → id de ATS → empresa+cargo exato → similaridade de tokens, contra `data/jobs/` e `applications.json`. |
| `engine/automation/scoring.py` | `fit_score` determinístico (categoria/localização/salário/recência), sem LLM. |
| `engine/automation/ingestion.py` | JD → `adapt_resume_with_llm`/`generate_job_materials` (PT/EN) → `JobPipeline.process_job_artifact(auto_activate=False)`. |
| `engine/automation/workflow.py` | Orquestra radar→dedupe→score→ingestão com teto de vagas adaptadas por ciclo (custo de LLM). |
| `engine/automation/queue_actions.py` | As ações por trás dos botões da Fila de Aprovação do Streamlit. |
| `engine/automation/tracking.py` | `register_application()` genérico — só chamado após confirmação real de envio. |
| `engine/application/` | Application Prep Agent: detecção de ATS, extração de campos do formulário, resolução de respostas (currículo → materiais → LLM com evidência → humano) e o clique de envio em si. |

### 5.3 Divisão cloud × local

| Onde | O quê | Por quê |
|---|---|---|
| **Cloud** (`.github/workflows/automation_cycle.yml`, agendado) | `scripts/run_automation_cycle.py`: radar → dedupe → score → adaptação. Sem intervenção humana, para em `AWAITING_RESUME_APPROVAL`. Abre PR contra `automation/radar-cycle` — **nunca** dá push em `main` diretamente (isso redeployaria o app público antes de qualquer revisão). | Só precisa de rede de saída (boards públicos + OpenRouter) e da `OPENROUTER_API_KEY` como secret do repositório — nenhuma credencial de login em nenhum site. |
| **Local** (sua máquina) | `scripts/run_application_agent.py` (Fase 5) e `scripts/run_submit_agent.py` (Fase 6): abrem um navegador Playwright de verdade contra o site real da vaga. | Alguns ATS exigem login/sessão; mesmo quando não exigem, clicar em "Enviar" é a ação mais sensível de todo o pipeline — não faz sentido rodar isso num runner efêmero sem supervisão. Nenhuma credencial/cookie de login é armazenada no GitHub. |

Fluxo típico ponta a ponta:
1. (Cloud, agendado ou `workflow_dispatch`) radar roda, abre PR com vagas novas em
   `AWAITING_RESUME_APPROVAL`.
2. Você revisa e faz merge do PR.
3. (Local) `streamlit run app.py` → aba "Fila de Aprovação (Radar)" → aprova o
   currículo de cada vaga que quiser seguir (Gate #1).
4. (Local) `python scripts/run_application_agent.py` — abre o formulário real,
   preenche o que conseguir com confiança, marca o resto como pendente de revisão
   humana. Termina em `AWAITING_APPLICATION_REVIEW`.
5. (Local, Streamlit) revisa os campos preenchidos/pendentes → "Marcar como pronta
   para envio" (`READY_TO_SUBMIT`) → "🚀 Aprovar envio" (Gate #2, `SUBMIT_APPROVED`).
6. (Local) `python scripts/run_submit_agent.py --yes` — repreenche o formulário do
   zero (determinístico, reproduz o mesmo resultado da Fase 5) e só então clica em
   enviar de verdade. Sem `--yes`, faz só um dry-run.

### 5.4 Configuração

- `automation_sources.json` — slugs dos boards Greenhouse/Lever/Ashby a monitorar
  (vazio por padrão; o radar não inventa empresas para acompanhar).
- `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` — mesmas variáveis do pipeline manual
  (seção 2), reaproveitadas pela adaptação automática.
- Localmente, `playwright install chromium` precisa ser rodado uma vez antes de usar
  `run_application_agent.py`/`run_submit_agent.py` (o ambiente de desenvolvimento
  deste projeto já vem com o Chromium pré-instalado; a sua máquina não).
