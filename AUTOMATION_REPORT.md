# Relatório de Implementação — Sprint de Automação do Career OS

Branch: `automation/sprint-foundation` · 8 commits, Fase 0 → Fase 8.

## O que foi construído

Uma camada de automação sobre o Career OS existente (`master_resume.json` →
`JobPipeline` → `data/jobs/<slug>.json` → Streamlit) que descobre vagas, filtra por
aderência determinística, roda a adaptação já existente (agora via OpenRouter em vez
de Gemini) e para em dois gates humanos estruturais antes de qualquer candidatura
real ser enviada. Nada do pipeline manual foi reescrito — a automação reaproveita
`job_store.validate_job`/`activate_job`, `JobPipeline.process_job_artifact`,
`utils.adapt_resume_with_llm`/`generate_job_materials` e o schema de
`applications.json`, tudo intocado.

## Correções feitas ao plano original antes de começar

O plano trazido pelo usuário foi revisado contra o código real do repositório
(clonado e inspecionado, não apenas contra a descrição do plano). Sete pontos
mudaram o desenho:

1. `fit_score` não era calculado por nada — o pipeline usava um placeholder fixo
   (95). Corrigido: `engine/automation/scoring.py` calcula e exige o valor real
   antes do pipeline rodar.
2. `JobPipeline` não adapta currículo — só valida/salva/ativa/exporta PDF. A
   automação precisou chamar `adapt_resume_with_llm`/`generate_job_materials`
   explicitamente (`engine/automation/ingestion.py`).
3. `AGENTS.md` manda dar `git push origin main` a cada adaptação (deploy do app
   público). A automação nunca poderia seguir essa regra sem revisão humana antes —
   por isso trabalha em branch própria + PR, nunca toca `main` diretamente (ver
   `.github/workflows/automation_cycle.yml` e a exceção explícita adicionada em
   `AGENTS.md`).
4. `app.py` não tinha nenhuma fila de vagas — a aba "Fila de Aprovação" (Fase 4) é
   funcionalidade nova, não um ajuste pequeno.
5. Não havia teto de custo/volume no radar — `max_jobs_per_cycle` (padrão 5) resolve
   isso em `engine/automation/workflow.py`.
6. `generate_job_materials` só devolve perguntas genéricas fixas — o
   `answer_engine.py` usa correspondência por similaridade (rapidfuzz), não índice
   exato, e nunca deixa a LLM "adivinhar" uma escolha em campos de seleção única.
7. Não existia pytest no repositório (só 3 scripts soltos na raiz, chamados
   manualmente). Infraestrutura de teste nova: `pytest.ini`, `tests/conftest.py`,
   `requirements-dev.txt`.

## Migração Gemini → OpenRouter (pedido do usuário, no meio do planejamento)

`llm_client.py` (novo) centraliza o backend de LLM via `instructor.from_provider()`
apontando para `https://openrouter.ai/api/v1`, mantendo os mesmos schemas Pydantic
de saída (`AdaptedResume`, `JobMaterials`, `ParsedJobPosting`, `JobTriples`) — o
comportamento de zero-alucinação não mudou, só o provedor por baixo. Modelo padrão
configurável via `OPENROUTER_MODEL` (`.env`), sem tocar em código para trocar.
`utils.adapt_resume_with_gemini` foi renomeada para `adapt_resume_with_llm`;
`engine/job_parser.py` (caminho do Knowledge Graph) migrou junto, por pedido
explícito.

## Fase a fase

| Fase | Entregável | Testes |
|---|---|---|
| 0 | Setup: branch, pytest, `requirements-dev.txt` | — |
| 0.5 | Migração Gemini → OpenRouter (`llm_client.py`, `utils.py`, `engine/job_parser.py`) | 6 |
| 1 | Máquina de estados explícita (`engine/automation/state_machine.py`) | 11 |
| 2 | Scoring determinístico + Radar (Greenhouse/Lever/Ashby) + Dedupe | 6 + 5 + 10 |
| 3 | Ingestão (`adapt_and_ingest`) + integração com `JobPipeline` | 6 |
| 4 | Fila de aprovação no Streamlit (Gate #1) | 4 + 12 |
| 5 | Application Prep Agent (Playwright): detecção de ATS, extração de campos, resolução de respostas | 6 + 8 + 11 + 5 |
| 6 | Gate de submit (Gate #2) + tracking genérico | 8 + 5 |
| 7 | Scheduler (GitHub Actions) + `run_automation_cycle.py` | 6 |
| 8 | Teste de integração ponta a ponta + relatório | 1 |

**Suíte completa: 115/115 testes passando.** Os 3 scripts de teste legados
(`test_graph.py`, `test_graph_rag.py`, `test_transferability.py`) continuam saindo
com código 0 — nenhuma regressão no caminho do Knowledge Graph.

Uma decisão importante de teste: a partir da Fase 5, os testes que envolvem
formulários/navegador rodam contra um **Chromium real headless** (via
`page.set_content`, sem rede) em vez de mockar objetos do Playwright — inclusive um
clique de botão real e a mutação de DOM resultante em `test_submit.py`. Isso é mais
fiel ao comportamento real do que qualquer mock teria sido.

## Bugs reais encontrados via TDD (não hipotéticos — cada um tem um teste de
regressão)

1. **Colisão de ID entre boards do Greenhouse** (`dedupe.py`): números de vaga do
   Greenhouse são únicos só por board, não globalmente. `extract_ats_id()` capturava
   só o número, causando falso-positivo de duplicata entre empresas diferentes.
2. **Status final nunca persistido em disco** (`ingestion.py`):
   `JobPipeline.process_job_artifact()` escreve o artefato com `workflow_status`
   ainda `VALIDATING`; a transição para `AWAITING_RESUME_APPROVAL` só mudava o
   dict em memória. A fila de aprovação (que lê direto do disco) nunca veria
   nenhuma vaga. Corrigido re-persistindo depois da transição final.
3. **Matching de aplicação existente quebrado com o prefixo `application:`**
   (`tracking.py`): `dedupe.find_duplicate()` devolve `"application:<id>"` para
   linhas do tracker sem `source_job_id` (entradas manuais pré-automação); a
   primeira versão de `register_application()` comparava esse valor direto contra
   `entry["id"]`, nunca batendo — uma reenvio duplicaria a linha do tracker em vez
   de atualizá-la.

## Os dois gates humanos (nunca puláveis por código)

- **Gate #1 — Aprovar currículo:** `AWAITING_RESUME_APPROVAL → RESUME_APPROVED`.
- **Gate #2 — Aprovar envio:** `READY_TO_SUBMIT → SUBMIT_APPROVED`. Só depois desse
  estado o `submit_application()` tem permissão de clicar em qualquer botão real —
  e mesmo assim só registra `APPLIED` se detectar um indicador real de sucesso na
  página resultante (um clique sem confirmação vira `FAILED`, nunca `APPLIED`).

Ambos são impostos pela tabela de transições explícita em `state_machine.py`
(`TRANSITIONS`), nunca inferidos por quais arquivos existem em disco — e o teste de
integração ponta a ponta (`tests/test_end_to_end_pipeline.py`) confirma que
`applications.json` continua vazio em *todos* os pontos anteriores ao envio
confirmado, inclusive logo depois do Gate #2.

## Limitações conhecidas deste ambiente (não do código)

- **Este sandbox de desenvolvimento não alcança `openrouter.ai`** (bloqueio de
  rede de saída do ambiente — confirmado via curl). A migração para OpenRouter foi
  validada com mocks (nenhum teste automatizado depende de rede), mas uma chamada
  real ponta-a-ponta com a `OPENROUTER_API_KEY` fornecida ainda precisa ser
  validada no seu ambiente local ou em CI (GitHub Actions normalmente tem saída de
  rede irrestrita).
- **Esta sessão Cowork não tem autorização de push/PR para
  `keevinvieeira/curriculo-kevin`** apesar do PAT fornecido ser válido (confirmado
  via `GET /user`, 200). O erro do proxy do Git menciona um mecanismo de
  autorização por repositório que não está disponível como ferramenta nesta sessão.
  Por isso, cada fase foi entregue como um **git bundle** enviado no chat — puxe-o
  para um clone local seu (`git fetch <bundle> automation/sprint-foundation:automation/sprint-foundation`)
  e abra o PR de lá.

## Antes de usar de verdade

1. Preencha `automation_sources.json` com os boards Greenhouse/Lever/Ashby reais que
   você quer monitorar (vazio por padrão).
2. Configure o secret `OPENROUTER_API_KEY` (e opcionalmente `OPENROUTER_MODEL`) no
   repositório do GitHub, para o workflow agendado funcionar.
3. Localmente, rode `playwright install chromium` uma vez antes de usar
   `scripts/run_application_agent.py`/`run_submit_agent.py`.
4. Revise e faça merge do PR com este trabalho antes de qualquer coisa — nada disso
   afeta `main`/o app público até você decidir.
