"""Career OS MCP — write tools and prompts (Fase 2), registered on the server from server.py."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import Field

from mcp_server import actions, queries
from mcp_server.server import READ_ONLY, RADAR_ID, WRITE, server

_ADAPTACAO_FORMATO = (
    "Formato (schema v2): {id?, metadata{company_name, role_title, url, fit_score, document_language, "
    "location, work_model, good_points, improvement_points}, triage{decision: adapt|hold|discard, notes, gaps, risks}, "
    "resume{pt, en} (AdaptedResume: name, location, phone, email, linkedin, summary, experience[{company, role, "
    "dates, location, bullets[]}], skills[{category, skills[]}], education, certifications, languages), "
    "materials{pt, en}{cover_letter, form_answers[{question, answer}]}, evidence{skills{pt, en}, "
    "requirements[{id, text, priority: must_have|nice_to_have, knockout?, status: covered|partial|gap, "
    "evidence_ids[], note?}], gaps[{requirement_id, severity: blocker|high|medium|low, detail, mitigation}], "
    "bullet_sources{pt, en}[{texto: bullet idêntico ao do resume, ids: [IDs do master]}]}."
)


@server.tool(
    title="Ler vaga salva",
    description="Devolve uma vaga adaptada salva em data/jobs (metadados, triagem, currículo, materiais e mapa de evidências).",
    annotations=READ_ONLY,
)
def ler_vaga(
    slug: Annotated[str, Field(description="Slug da vaga, ex.: wellhub-gtm-program-manager-revenue-operations")],
    idioma: Annotated[Literal["pt", "en", "ambos"], Field(description="Idioma dos textos")] = "ambos",
) -> dict[str, Any]:
    return queries.read_job(slug, idioma)


@server.tool(
    title="Validar adaptação",
    description=(
        "Guardrail anti-invenção. Checa a adaptação contra o master_resume: todo bullet tem fontes em "
        "evidence.bullet_sources com IDs existentes; todo número de um bullet aparece nos IDs citados; números do "
        "resumo existem no master; empresas e cargos batem com o master; mapa de evidências válido. Devolve "
        "{ok, erros, avisos}. Se houver erros, corrija a adaptação e valide de novo antes de salvar. "
        + _ADAPTACAO_FORMATO
    ),
    annotations=READ_ONLY,
)
def validar_adaptacao(
    vaga: Annotated[dict[str, Any] | str, Field(description="Objeto da adaptação, ou slug de uma vaga salva")],
) -> dict[str, Any]:
    return actions.validate(vaga)


@server.tool(
    title="Salvar adaptação",
    description=(
        "Valida e grava a adaptação em data/jobs/<slug>.json (schema v2). Não grava se a validação falhar "
        "(devolve os erros) nem sobrescreve uma vaga existente sem sobrescrever=true. " + _ADAPTACAO_FORMATO
    ),
    annotations=WRITE,
)
def salvar_adaptacao(
    vaga: Annotated[dict[str, Any], Field(description="Objeto completo da adaptação")],
    sobrescrever: Annotated[bool, Field(description="Substituir vaga já salva com o mesmo slug")] = False,
) -> dict[str, Any]:
    return actions.save(vaga, sobrescrever=sobrescrever)


@server.tool(
    title="Gerar PDF",
    description=(
        "Gera os PDFs do currículo adaptado (e da carta) de uma vaga salva, em exports/curriculos_vagas/<slug>/. "
        "Revalida antes; não gera se a adaptação tiver erros."
    ),
    annotations=WRITE,
)
def gerar_pdf(
    slug: Annotated[str, Field(description="Slug da vaga salva")],
    idiomas: Annotated[Optional[list[Literal["pt", "en"]]], Field(description="Padrão: pt e en")] = None,
    incluir_carta: Annotated[bool, Field(description="Gerar também a carta de apresentação")] = True,
) -> dict[str, Any]:
    return actions.render_pdfs(slug, idiomas=idiomas, incluir_carta=incluir_carta)


@server.tool(
    title="Registrar candidatura",
    description=(
        "Marca como aplicada em applications.json (status Candidatado, com data e histórico). Use SÓ depois que o "
        "Kevin confirmar que enviou. Informe o slug da vaga salva, ou empresa/cargo/url para vaga sem adaptação. "
        "Se a candidatura já existir, não duplica e devolve a existente."
    ),
    annotations=WRITE,
)
def registrar_candidatura(
    slug: Annotated[Optional[str], Field(description="Slug da vaga salva em data/jobs")] = None,
    empresa: Annotated[str, Field(description="Empresa (se não houver slug)")] = "",
    cargo: Annotated[str, Field(description="Cargo (se não houver slug)")] = "",
    url: Annotated[str, Field(description="Link da vaga (se não houver slug)")] = "",
    data: Annotated[Optional[str], Field(description="Data do envio AAAA-MM-DD (padrão: hoje)")] = None,
    notas: Annotated[str, Field(description="Observações da candidatura")] = "",
) -> dict[str, Any]:
    return actions.register(slug=slug, empresa=empresa, cargo=cargo, url=url, data=data, notas=notas)


@server.tool(
    title="Atualizar status",
    description=(
        "Muda o status de uma candidatura (Candidatado, Triagem, Entrevista, Proposta, Rejeitado, Desistente), "
        "registrando data e nota no histórico. Use o id devolvido por listar_candidaturas."
    ),
    annotations=WRITE,
)
def atualizar_status(
    candidatura_id: Annotated[str, Field(description="id da candidatura em applications.json")],
    status: Annotated[Literal["Candidatado", "Triagem", "Entrevista", "Proposta", "Rejeitado", "Desistente"],
                      Field(description="Novo status")],
    data: Annotated[Optional[str], Field(description="Data da mudança AAAA-MM-DD (padrão: hoje)")] = None,
    nota: Annotated[str, Field(description="O que aconteceu (ex.: 'convite para entrevista com gestor')")] = "",
    etapa_atual: Annotated[Optional[str], Field(description="Texto livre da etapa atual")] = None,
) -> dict[str, Any]:
    return actions.update_status(candidatura_id, status, data=data, nota=nota, etapa_atual=etapa_atual)


@server.prompt(title="Rotina diária do Career OS",
               description="Vagas novas → adapta → valida → PDFs → fila de inscrição por fit.")
def rotina_diaria(quantidade: str = "5") -> str:
    return f"""Rode o Career OS de hoje.

1. Leia a planilha "Radar de Vagas — Kevin" pelo conector do Google Drive (id {RADAR_ID}) e passe as linhas
   para `vagas_novas`. Mostre o resumo (novas, já aplicadas, descartadas) e os avisos de `atencao`.
2. Das novas, pegue as {quantidade} de maior fit. Para cada uma:
   a. Obtenha a descrição da vaga pelo link. Se estiver inacessível, diga isso e pule; não invente requisitos.
   b. `ler_master_resume` e monte a adaptação v2 em pt e en: triagem honesta, mapa de evidências
      (requisito → IDs do master, gaps com mitigação), currículo e carta, e `bullet_sources` para cada bullet.
      Só reescreva fatos do master; cargos seguem os títulos do master (título funcional em vez de "fundador").
   c. `validar_adaptacao`; corrija até não haver erros. Depois `salvar_adaptacao` e `gerar_pdf`.
3. Entregue a fila de inscrição em ordem de fit: empresa, cargo, fit, link, caminhos dos PDFs, principais gaps
   e o que responder sobre eles.
4. Não envie nenhuma candidatura. Quando o Kevin disser que enviou, use `registrar_candidatura`.
"""


@server.prompt(title="Preparar entrevista",
               description="Dossiê da empresa e roteiro de respostas para uma candidatura em entrevista.")
def preparar_entrevista(empresa: str) -> str:
    return f"""Prepare o Kevin para a entrevista na {empresa}.

1. `listar_candidaturas` com busca="{empresa}": etapa atual, histórico e notas. Se houver `slug_vaga`, use
   `ler_vaga` para recuperar requisitos, mapa de evidências e gaps.
2. Dossiê da empresa (pesquise na web e cite as fontes): produto, modelo de negócio, clientes, momento
   (rodadas, lançamentos, notícias recentes), concorrentes e o que o time/área da vaga faz.
3. Roteiro de respostas, sempre ancorado em IDs do master (`ler_master_resume`):
   - pitch de 60–90 segundos ligando a trajetória à vaga;
   - 4–6 histórias no formato STAR para os requisitos principais, citando o ID de cada fato;
   - respostas honestas para cada gap (sem prometer o que o master não comprova);
   - perguntas para o entrevistador adequadas à etapa (RH, gestor, técnica).
4. Se a entrevista for em inglês, entregue o pitch e as histórias também em inglês.
5. Ao final, pergunte se deve usar `atualizar_status` para registrar a etapa.
"""
