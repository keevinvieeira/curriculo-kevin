# Regras do Projeto de Curriculo

## Objetivo

Este workspace adapta o curriculo mestre de Kevin Augusto Vieira para vagas especificas e publica automaticamente a adaptacao no aplicativo Streamlit local.

`master_resume.json` e a fonte unica de verdade. Nunca invente experiencias, cargos, ferramentas, senioridade, metricas, idiomas, disponibilidade ou resultados.

## Gatilho Automatico

Sempre que o usuario enviar um link de vaga, uma descricao de vaga ou ambos, inicie imediatamente o fluxo completo abaixo. Nao pergunte o que o usuario deseja fazer e nao pare apenas em uma analise de compatibilidade.

Considere expressoes como "adapte", "essa vaga", "conforme as regras" ou apenas o envio do anuncio como autorizacao para:

1. Analisar e triar a vaga.
2. Adaptar o curriculo em portugues e ingles.
3. Gerar carta e respostas de candidatura nos dois idiomas.
4. Validar o artefato.
5. Ativar a vaga no Streamlit.
6. Confirmar que o aplicativo exibe a nova vaga, e nao dados mantidos da vaga anterior.

Se houver apenas um link, tente obter a descricao com as ferramentas disponiveis. So solicite o texto ao usuario se o conteudo estiver inacessivel, exigir autenticacao ou nao contiver informacoes suficientes para uma adaptacao responsavel.

## Fluxo Obrigatorio

### 1. Ler as fontes

- Leia `master_resume.json` antes de escrever a adaptacao.
- Leia `job_store.py` e use o schema dos artefatos existentes em `data/jobs/`.
- Consulte `MAPA.md` apenas como indice auxiliar; em caso de divergencia, prevalece `master_resume.json`.
- Nao use o grafo para adicionar fatos ausentes do curriculo mestre.

### 2. Fazer a triagem

- Extraia cargo, empresa, idioma principal, localizacao, modalidade, remuneracao, prazo, requisitos e responsabilidades.
- Registre `fit_score`, pontos fortes, lacunas, riscos, prazo e incompatibilidades salariais.
- Use `triage.decision` igual a `adapt`, salvo impedimento concreto que torne a candidatura impossivel.
- Mesmo com lacunas, produza a adaptacao quando houver aderencia transferivel razoavel.
- Nunca apresente uma competencia transferivel como experiencia direta na ferramenta exigida.

### 3. Criar o artefato versionado

- Crie `data/jobs/<slug-da-vaga>.json`.
- Preencha `metadata`, `triage`, `resume.pt`, `resume.en`, `materials.pt`, `materials.en` e `evidence.skills`.
- O idioma principal do anuncio deve ser `metadata.document_language`.
- Produza curriculos ATS concisos, priorizando Wipro, Meu Barzin, AK Branding e Munzner conforme a relevancia.
- Reescreva bullets para destacar aderencia, mas preserve fatos, datas, empresas e metricas comprovadas.
- Cargos adaptados devem descrever a funcao real e nao podem conter `Founder`, `Co-Founder`, `Fundador` ou `Cofundador`, conforme `job_store.py`.
- Skills declaradas em `evidence.skills` devem existir literalmente no idioma correspondente de `master_resume.json`.

### 4. Gerar materiais

- Gere uma carta curta e especifica, mencionando a empresa-alvo exatamente como aparece em `metadata.company_name`.
- Gere respostas para as perguntas mais provaveis da candidatura, incluindo lacunas relevantes de forma honesta.
- Quando houver faixa salarial, proponha um valor coerente e registre divergencias em `metadata.improvement_points` e `triage.notes`.
- Nao afirme disponibilidade de 40 horas, fuso horario, inicio imediato ou fluencia se isso nao estiver documentado ou confirmado.

### 5. Validar e ativar

- Verifique a sintaxe JSON.
- Execute:

```powershell
python scripts/activate_job.py <slug-da-vaga> --validate
```

- Se o `python` ativo nao tiver as dependencias necessarias no Windows, use explicitamente `py -3.12`.
- Corrija todos os erros de validacao antes de concluir.
- A ativacao deve atualizar automaticamente:
  - `data/jobs/active.json`
  - `metadata.json`
  - `adapted_resume.json`
  - `adapted_resume_pt.json`
  - `adapted_resume_en.json`
  - `job_materials.json`
  - `job_materials_pt.json`
  - `job_materials_en.json`

### 6. Publicar no Streamlit

- Considere a vaga publicada apenas depois que `data/jobs/active.json` apontar para o novo slug e os arquivos de compatibilidade contiverem a nova adaptacao.
- O `app.py` deve invalidar `st.session_state.adapted_resume` e `st.session_state.job_materials` quando mudar o par `(active_job_id, document_language)`.
- Se o Streamlit estiver em execucao, preserve o processo e confirme que a troca da vaga provoca recarga.
- Se nao houver processo local, inicie o app com:

```powershell
py -3.12 -m streamlit run app.py --server.headless true
```

- Use um processo em background rastreado para o servidor; nunca use `&`, `nohup` ou processos soltos.
- Verifique os logs de inicializacao e sempre informe a URL local clicavel, normalmente `http://localhost:8501`, para que o usuario visualize e baixe o curriculo adaptado.
- Sempre inclua tambem um link clicavel para abrir a pasta local dos arquivos entregues. Quando os arquivos forem publicados no repositorio, inclua o link web da pasta no GitHub para acesso fora da maquina local.

## Criterios de Qualidade

- A adaptacao deve maximizar aderencia sem fabricar experiencia.
- Lacunas em ferramentas especificas devem aparecer na triagem e, quando relevantes, nas respostas de candidatura.
- Prazos expirados e remuneracao abaixo da expectativa nao impedem automaticamente a adaptacao, mas devem ser destacados.
- Nao modifique nem reverta alteracoes nao relacionadas existentes no workspace.
- Nao registre a candidatura em `applications.json` sem pedido explicito do usuario; ativar no Streamlit nao significa marcar como candidatado.

## Resposta Final Padrao

Ao concluir, informe de forma objetiva:

- Vaga e empresa ativadas.
- Fit estimado e principal posicionamento.
- Artefato versionado criado.
- Validacao realizada.
- Status do Streamlit e link clicavel do servidor para visualizar e baixar o curriculo adaptado.
- Link clicavel para abrir a pasta local da entrega e, quando disponivel, a pasta publicada no GitHub.
- Lacunas ou alertas importantes, sem transformar a resposta em uma nova pergunta.
