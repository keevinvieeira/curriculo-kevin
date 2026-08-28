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

### 6. Publicar Online e Sincronizar no GitHub

- Toda adaptacao e compilacao de PDFs deve ser imediatamente sincronizada via `git push origin main` para deploy automatico no projeto online.
- Nao e necessario iniciar ou manter servidores locais do Streamlit em segundo plano; o fluxo oficial e direto no projeto online e no GitHub.
- Sempre inclua os links clicaveis para download dos PDFs gerados e o link web do repositorio no GitHub: `https://github.com/keevinvieeira/curriculo-kevin`.

## Criterios de Qualidade

- A adaptacao deve maximizar aderencia sem fabricar experiencia.
- NUNCA inclua frases negativas, declaracoes de carencia, limitacoes defensivas ou gaps nos resumos profissionais, bullets de experiencia, habilidades ou cartas de apresentacao (ex.: jamais usar frases como 'sem alegar experiencia direta em X'). O curriculo e a apresentacao publica devem ser 100% positivos, orientados a valor, metricas reais e competencias comprovadas.
- Lacunas tecnicas internas podem ser mantidas apenas no diagnostico interno de triagem para preparacao de entrevistas, mas nunca sao exibidas ou impressas no curriculo/PDF.
- Educacao Obrigatoria: Sempre incluir o Bacharelado e Licenciatura em Filosofia (UFPR) e a Formacao em Engenharia (UFPR/UTFPR - Incompleto / 2,5 anos cursados). NUNCA incluir a Especializacao em Filosofia Clinica nos curriculos adaptados.
- Experiencia Conversas Brasileiras: O cargo oficial e sempre 'Especialista em Marketing de Comunidades' / 'Community Marketing Specialist' (nunca 'Co-Founder' ou 'Fundador').
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
