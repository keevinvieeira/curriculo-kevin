"""Fase 2: grounding guardrail and MCP write actions (save, PDF, register, status)."""
from __future__ import annotations

import copy
import json

import pytest

import job_store
from engine.automation import tracking
from grounding import validate_grounding
from job_store import ROOT, read_json
from mcp_server import actions

WIPRO_ROLE_PT = "Especialista em Operações de Marketing / GTM e Sales Enablement (Projeto Meta)"
WIPRO_ROLE_EN = "Marketing Operations / GTM & Sales Enablement Specialist (Meta Project)"


def _resume(lang: str, bullets: list[str], role: str) -> dict:
    return {
        "name": "Kevin Augusto Vieira", "location": "Curitiba", "phone": "+55", "email": "k@example.com",
        "linkedin": "linkedin.com/in/kevin-augusto", "summary": "Especialista em GTM com IA aplicada.",
        "experience": [{"company": "Wipro", "role": role, "dates": "2024 – 2026", "bullets": bullets}],
        "skills": [{"category": "CRM", "skills": ["n8n"]}],
        "education": [], "certifications": [], "languages": [],
    }


@pytest.fixture
def master():
    return read_json(ROOT / "master_resume.json")


@pytest.fixture
def grounded_job():
    evidence = read_json(ROOT / "data" / "schemas" / "examples" / "wellhub-evidence-map.json")
    bullet_pt = "Elevou o uso de IA no CRM da Meta de 4 para 10 prompts/dia por consultor (+150%)."
    bullet_en = "Raised AI usage in Meta's CRM from 4 to 10 prompts/day per consultant (+150%)."
    evidence["bullet_sources"] = {"pt": [{"texto": bullet_pt, "ids": ["wipro-b05"]}],
                                  "en": [{"texto": bullet_en, "ids": ["wipro-b05"]}]}
    return {
        "metadata": {"company_name": "Acme Test", "role_title": "GTM Specialist", "url": "https://acme.test/jobs/1",
                     "document_language": "pt", "fit_score": 88},
        "triage": {"decision": "adapt", "notes": [], "gaps": [], "risks": []},
        "resume": {"pt": _resume("pt", [bullet_pt], WIPRO_ROLE_PT), "en": _resume("en", [bullet_en], WIPRO_ROLE_EN)},
        "materials": {lang: {"cover_letter": "Olá, time da Acme Test.", "form_answers": []} for lang in ("pt", "en")},
        "evidence": evidence,
    }


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    apps = tmp_path / "applications.json"
    apps.write_text(json.dumps([{"id": "7", "company": "Old Co", "role": "PMM", "status": "Entrevista",
                                 "url": "https://old.co/jobs/9", "date_applied": "2026-09-01",
                                 "status_history": [{"status": "Candidatado", "date": "2026-09-01"}]}]),
                    encoding="utf-8")
    monkeypatch.setattr(job_store, "JOBS_DIR", jobs)
    monkeypatch.setattr(tracking, "APPLICATIONS_PATH", apps)
    monkeypatch.setattr(actions, "EXPORTS_DIR", tmp_path / "exports")
    return tmp_path


# --- grounding ----------------------------------------------------------------

def test_grounded_adaptation_passes(grounded_job, master):
    errors, _ = validate_grounding(grounded_job, master)
    assert errors == []


@pytest.mark.parametrize("mutate, expected", [
    (lambda j: j["resume"]["pt"]["experience"][0]["bullets"].append("Bullet sem fonte."), "sem entrada em evidence.bullet_sources"),
    (lambda j: j["evidence"]["bullet_sources"]["pt"][0].update(ids=["wipro-b99"]), "IDs inexistentes"),
    (lambda j: j["evidence"]["bullet_sources"]["pt"][0].update(ids=["wipro-b01"]), "números ausentes"),
    (lambda j: j["resume"]["pt"].update(summary="Mais de 300 projetos entregues."), "números que não existem no master"),
    (lambda j: j["resume"]["pt"]["experience"][0].update(company="Google"), "empresa não encontrada"),
    (lambda j: j["resume"]["pt"]["experience"][0].update(role="Diretor de Engenharia de Dados"), "não corresponde a nenhum cargo"),
    (lambda j: j["evidence"].update(requirements=[]), "evidence.requirements está vazio"),
])
def test_grounding_blocks_invented_facts(grounded_job, master, mutate, expected):
    mutate(grounded_job)
    errors, _ = validate_grounding(grounded_job, master)
    assert any(expected in e for e in errors), errors


def test_bullet_number_rewritten_differently_still_matches(grounded_job, master):
    # "43,9%" in the master vs "43.9%" in an English bullet; "~R$ 50k" vs "R$ 50,000".
    bullet = "Mapped conversion barriers: API latency caused 43.9% first-message dropout."
    grounded_job["resume"]["en"]["experience"][0]["bullets"] = [bullet]
    grounded_job["evidence"]["bullet_sources"]["en"] = [{"texto": bullet, "ids": ["meu-barzin-b07"]}]
    grounded_job["resume"]["en"]["experience"][0].update(company="Meu Barzin", role="Product Manager & GTM")
    errors, _ = validate_grounding(grounded_job, master)
    assert errors == []


def test_translated_and_functional_titles_pass_but_embellishment_warns(grounded_job, master):
    exp = grounded_job["resume"]["pt"]["experience"][0]
    exp.update(company="AK Branding & Web Design", role="Consultor de Projetos de Marketing")
    grounded_job["evidence"]["bullet_sources"]["pt"][0]["ids"] = ["wipro-b05"]
    errors, warnings = validate_grounding(grounded_job, master)
    assert not [e for e in errors if "cargo" in e]

    exp["role"] = "Consultor de Projetos de Marketing e Automação"
    errors, warnings = validate_grounding(grounded_job, master)
    assert not [e for e in errors if "cargo" in e]
    assert any("automacao" in w for w in warnings)


# --- write actions ------------------------------------------------------------

def test_save_blocks_invalid_and_never_overwrites_silently(grounded_job, sandbox):
    broken = copy.deepcopy(grounded_job)
    broken["evidence"]["bullet_sources"] = {}
    result = actions.save(broken)
    assert result["salvo"] is False and result["erros"]
    assert not list((sandbox / "jobs").iterdir())

    saved = actions.save(grounded_job)
    assert saved["salvo"] is True and saved["slug"] == "acme-test-gtm-specialist"
    stored = read_json(sandbox / "jobs" / "acme-test-gtm-specialist.json")
    assert stored["schema_version"] == 2

    again = actions.save(grounded_job)
    assert again["salvo"] is False and "sobrescrever" in again["erros"][0]
    assert actions.save(grounded_job, sobrescrever=True)["salvo"] is True


def test_render_pdfs(grounded_job, sandbox):
    pytest.importorskip("xhtml2pdf")
    actions.save(grounded_job)
    result = actions.render_pdfs("acme-test-gtm-specialist", idiomas=["pt"])
    assert result["gerado"] is True
    names = sorted(p.split("\\")[-1].split("/")[-1] for p in result["arquivos"])
    assert names == ["carta_pt.pdf", "curriculo_pt.pdf"]
    assert (sandbox / "exports" / "acme-test-gtm-specialist" / "curriculo_pt.pdf").read_bytes()[:4] == b"%PDF"


def test_register_then_duplicate_then_status(grounded_job, sandbox):
    actions.save(grounded_job)
    first = actions.register(slug="acme-test-gtm-specialist", data="2026-09-24")
    assert first["registrado"] is True and first["candidatura"]["status"] == "Candidatado"

    dup = actions.register(empresa="Acme Test", cargo="GTM Specialist", url="https://acme.test/jobs/1")
    assert dup["registrado"] is False and dup["candidatura"]["id"] == first["candidatura"]["id"]

    in_process = actions.register(empresa="Old Co", cargo="PMM", url="https://old.co/jobs/9")
    assert in_process["registrado"] is False and in_process["candidatura"]["status"] == "Entrevista"

    moved = actions.update_status(first["candidatura"]["id"], "Rejeitado", data="2026-09-30", nota="negativa por e-mail")
    assert [h["status"] for h in moved["historico"]] == ["Candidatado", "Rejeitado"]
    assert moved["historico"][0]["source"] == "mcp"
    stored = next(a for a in read_json(sandbox / "applications.json") if a["id"] == first["candidatura"]["id"])
    assert stored["date_rejected"] == "2026-09-30" and "negativa por e-mail" in stored["notes"]


def test_update_status_rejects_unknown_values(sandbox):
    with pytest.raises(ValueError, match="status inválido"):
        actions.update_status("7", "Contratado")
    with pytest.raises(ValueError, match="não encontrada"):
        actions.update_status("999", "Triagem")
