"""Career OS MCP server — read tools (Fase 1), write tools and prompts (Fase 2).

The server does not reason; it reads, dedupes and reports exactly. Choosing what to
highlight and writing the adaptation stay with Claude.
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from mcp_server import queries

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
RADAR_ID = os.environ.get("CAREER_OS_RADAR_ID", "1hav62sxd66E__QvM3bqml1tJuG8pAfNq21gupR9yFfs")

server = MCPServer(
    name="career-os",
    title="Career OS",
    instructions=(
        "Career OS do Kevin Augusto Vieira. master_resume.json é a fonte única de verdade: "
        "nunca afirme experiência, cargo, ferramenta ou métrica que não esteja nele. "
        "Ao mapear uma vaga, cite os IDs devolvidos por ler_master_resume (ex.: wipro-b05); "
        "o que não tiver ID que comprove é gap. Status de candidatura: "
        "Candidatado, Triagem, Entrevista, Proposta, Rejeitado, Desistente; "
        "'sem resposta' é derivado (Candidatado parado há dias). "
        "Nunca envie candidatura: login, CAPTCHA e o clique final de enviar são sempre do Kevin; "
        "registre só depois que ele confirmar o envio."
    ),
)


@server.tool(
    title="Ler currículo mestre",
    description=(
        "Devolve o master_resume.json com IDs estáveis. Use antes de adaptar um currículo ou montar "
        "o mapa de evidências de uma vaga. formato='evidencias' (padrão) traz a lista enxuta de itens "
        "citáveis — {id, tipo, empresa, texto} — que é o que o mapa de evidências referencia. "
        "formato='completo' traz o JSON inteiro (grande: filtre com `secoes` e `idioma`)."
    ),
    annotations=READ_ONLY,
)
def ler_master_resume(
    formato: Annotated[Literal["evidencias", "completo"], Field(description="evidencias (padrão) ou completo")] = "evidencias",
    idioma: Annotated[Literal["pt", "en", "ambos"], Field(description="Idioma dos textos")] = "pt",
    secoes: Annotated[Optional[list[str]], Field(description=(
        "Só com formato=completo: seções a devolver, ex. ['work_experience', 'technical_skills']"))] = None,
) -> dict[str, Any]:
    return queries.read_master(formato=formato, idioma=idioma, secoes=secoes)


@server.tool(
    title="Vagas novas",
    description=(
        "Recebe a lista de vagas da planilha e devolve só as novas, ordenadas por fit (maior primeiro). "
        "Remove o que já está em applications.json (ja_aplicadas) e o que foi descartado; separa o que "
        "já foi adaptado em data/jobs mas não aplicado (ja_adaptadas). Passe as linhas em `vagas` "
        "(ex.: lidas pelo conector do Google Drive) ou um arquivo local .xlsx/.csv em `planilha`; sem "
        "nenhum dos dois, usa a variável de ambiente CAREER_OS_PLANILHA. Colunas reconhecidas: "
        "empresa/company, cargo/vaga/title, url/link, fit/score (0-10 ou 0-100), Aplicada, Status no Radar. "
        "Vagas novas de empresas com candidatura em aberto vêm com o campo `atencao`."
    ),
    annotations=READ_ONLY,
)
def vagas_novas(
    vagas: Annotated[Optional[list[dict[str, Any]]], Field(description=(
        "Linhas da planilha, cada uma um objeto coluna→valor"))] = None,
    planilha: Annotated[Optional[str], Field(description="Caminho de um .xlsx ou .csv local")] = None,
    limite: Annotated[int, Field(ge=1, le=200, description="Máximo de vagas novas devolvidas")] = 30,
) -> dict[str, Any]:
    return queries.new_jobs(vagas=vagas, planilha=planilha or os.environ.get("CAREER_OS_PLANILHA"), limite=limite)


@server.tool(
    title="Listar candidaturas",
    description=(
        "Mostra o funil de candidaturas (contagem por status) e a lista filtrada, com histórico datado "
        "de status e dias desde a última movimentação. Use para perguntas como 'como está meu funil', "
        "'quais estão em entrevista', 'quais estão sem resposta'."
    ),
    annotations=READ_ONLY,
)
def listar_candidaturas(
    status: Annotated[Optional[list[str]], Field(description=(
        "Filtra por status: Candidatado, Triagem, Entrevista, Proposta, Rejeitado, Desistente"))] = None,
    sem_resposta: Annotated[bool, Field(description=(
        "Só as que estão como Candidatado sem movimentação há sem_resposta_dias ou mais"))] = False,
    sem_resposta_dias: Annotated[int, Field(ge=1, description="Dias parado para contar como sem resposta")] = queries.SEM_RESPOSTA_DIAS_PADRAO,
    busca: Annotated[str, Field(description="Texto contido na empresa ou no cargo")] = "",
    desde: Annotated[Optional[str], Field(description="Só candidaturas a partir desta data (AAAA-MM-DD)")] = None,
) -> dict[str, Any]:
    return queries.list_applications(status=status, sem_resposta=sem_resposta,
                                     sem_resposta_dias=sem_resposta_dias, busca=busca, desde=desde)


# Write tools and prompts register themselves on `server` when imported.
from mcp_server import escrita  # noqa: E402,F401
