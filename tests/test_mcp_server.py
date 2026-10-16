"""Fase 1: read-only Career OS MCP server."""
from __future__ import annotations

import datetime

import pytest
from mcp.client import Client
from openpyxl import Workbook

from mcp_server import queries
from mcp_server.server import server

APPLICATIONS = [
    {"id": "1", "company": "Starian", "role": "Product Marketing Sênior", "status": "Entrevista",
     "url": "https://starian.gupy.io/jobs/12374141", "date_applied": "2026-09-09",
     "status_history": [{"status": "Candidatado", "date": "2026-09-09"}, {"status": "Entrevista", "date": "2026-09-10"}]},
    {"id": "2", "company": "Acme", "role": "Growth Marketer", "status": "Candidatado", "url": "",
     "date_applied": "2026-09-01", "status_history": [{"status": "Candidatado", "date": "2026-09-01"}]},
]
JOBS = [
    {"id": "olist-gtm", "metadata": {"company_name": "Olist", "role_title": "Especialista GTM ERP", "url": ""},
     "triage": {"decision": "adapt"}},
    {"id": "foo-pm", "metadata": {"company_name": "Foo", "role_title": "Product Manager", "url": ""},
     "triage": {"decision": "discard"}},
]


# --- master -------------------------------------------------------------------

def test_evidence_list_is_citable_and_skips_restatements():
    items = queries.read_master()["pt"]
    ids = {item["id"] for item in items}
    assert {"wipro-b05", "meu-barzin-b07", "lang-english", "edu-ufpr-filosofia"} <= ids
    assert "ai-career-os-r01" not in ids  # same_as ai-career-os-b01
    assert all(item["texto"] for item in items)


def test_full_master_in_one_language():
    data = queries.read_master(formato="completo", idioma="en", secoes=["languages", "work_experience"])
    assert set(data) == {"languages", "work_experience"}
    assert "pt" not in data["languages"]
    bullet = data["work_experience"][1]["bullets"][0]
    assert "en" in bullet and "pt" not in bullet and bullet["id"] == "wipro-b01"


def test_unknown_section_is_explained():
    with pytest.raises(ValueError, match="seções inexistentes"):
        queries.read_master(formato="completo", secoes=["nope"])


# --- new jobs -----------------------------------------------------------------

def test_classify_jobs_buckets_and_orders_by_fit():
    rows = [
        {"Empresa": "Starian", "Cargo": "Analista de PMM Pl",
         "Link": "https://starian.gupy.io/jobs/12374141?jobBoardSource=gupy_public_page"},
        {"company": "Olist", "title": "Especialista GTM ERP"},
        {"Empresa": "Foo", "Vaga": "Product Manager"},
        {"Empresa": "Beta", "Cargo": "RevOps", "Fit": "72%"},
        {"Empresa": "Gama", "Cargo": "PMM", "Fit": 0.91},
        {"Empresa": "Gama", "Cargo": "PMM", "Fit": 0.91},  # repeated row in the sheet
        {"Empresa": "Delta", "Cargo": "Ops"},
        {"Empresa": "", "Cargo": "Sem empresa"},
        {"Empresa": "Docplanner", "Cargo": "Product Ops", "Status no Radar": "Encerrada", "Aplicada": "FALSE"},
        {"Empresa": "Zeta", "Cargo": "PMM", "Aplicada": "TRUE"},
        {"Empresa": "Acme", "Cargo": "Head of Growth"},
    ]
    result = queries.classify_jobs(rows, JOBS, APPLICATIONS)
    assert [r["empresa"] for r in result["novas"]] == ["Gama", "Beta", "Delta", "Acme"]
    assert result["novas"][-1]["atencao"].startswith("Candidatura em aberto na mesma empresa: #2")
    assert result["novas"][0]["fit"] == 91.0
    assert queries._parse_fit("9,5") == 95.0 and queries._parse_fit(87) == 87.0
    assert [r["match"] for r in result["ja_aplicadas"]] == ["application:1", "planilha: Aplicada"]
    assert [r["match"] for r in result["ja_adaptadas"]] == ["olist-gtm"]
    assert [r["match"] for r in result["descartadas"]] == ["foo-pm", "planilha: Encerrada"]
    assert len(result["incompletas"]) == 1


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_read_sheet_from_local_file(tmp_path, suffix):
    path = tmp_path / f"vagas{suffix}"
    header, row = ["Empresa", "Cargo", "Fit"], ["Beta", "RevOps", 80]
    if suffix == ".csv":
        path.write_text("Empresa,Cargo,Fit\nBeta,RevOps,80\n", encoding="utf-8")
    else:
        book = Workbook()
        book.active.append(header)
        book.active.append(row)
        book.active.append([None, None, None])
        book.save(path)
    rows = queries.read_sheet(path)
    assert len(rows) == 1 and rows[0]["Empresa"] == "Beta"


def test_new_jobs_without_source_explains_both_options():
    with pytest.raises(ValueError, match="conector do Google Drive"):
        queries.new_jobs()


# --- applications -------------------------------------------------------------

def test_list_applications_funnel_and_no_answer(monkeypatch):
    monkeypatch.setattr(queries, "read_json", lambda path: APPLICATIONS)
    result = queries.list_applications(sem_resposta=True, hoje=datetime.date(2026, 9, 24))
    assert result["funil"]["Entrevista"] == 1
    assert [r["empresa"] for r in result["candidaturas"]] == ["Acme"]
    assert result["candidaturas"][0]["dias_parado"] == 23

    only_interview = queries.list_applications(status=["entrevista"], hoje=datetime.date(2026, 9, 24))
    assert [r["empresa"] for r in only_interview["candidaturas"]] == ["Starian"]
    assert only_interview["candidaturas"][0]["ultima_movimentacao"] == "2026-09-10"


# --- MCP wiring ---------------------------------------------------------------

def _run_in_thread(coro_fn):
    """The session-scoped sync Playwright fixture (conftest.py) keeps an event loop
    running on the main thread, so the MCP client gets a thread of its own."""
    import anyio
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(anyio.run, coro_fn).result()


def test_tools_are_exposed_read_only():
    async def scenario():
        async with Client(server, raise_exceptions=True) as client:
            tools = {tool.name: tool for tool in (await client.list_tools()).tools}
            result = await client.call_tool("listar_candidaturas", {"busca": "starian"})
            return tools, result

    tools, result = _run_in_thread(scenario)
    read = {"ler_master_resume", "vagas_novas", "listar_candidaturas", "ler_vaga", "validar_adaptacao"}
    write = {"salvar_adaptacao", "gerar_pdf", "registrar_candidatura", "atualizar_status"}
    assert set(tools) == read | write
    assert all(tools[name].annotations.read_only_hint for name in read)
    assert not any(tools[name].annotations.read_only_hint for name in write)
    assert not result.is_error
    assert result.structured_content["candidaturas"][0]["empresa"] == "Starian"
