"""End-to-end integration test (Fase 8's "Verificação" requirement): one posting
walking the *entire* automation pipeline, module by module, exactly as the real
scripts would drive it — radar posting -> dedupe -> score -> ingestion -> Gate #1 ->
Application Prep Agent -> Gate #2 -> submit -> tracking.

Asserts the two hard invariants from the original plan at every step:
  1. No transition ever skips a gate (each step's `get_workflow_status` matches
     exactly what that step is supposed to produce, no more, no less).
  2. `applications.json` receives an entry only after a real (simulated) submit
     confirmation — never before, not even after Gate #2 approval.

Real headless Chromium is used for the application-form steps (no LLM/network); the
LLM calls (résumé/materials adaptation) are mocked, same as the rest of the suite.
"""
from __future__ import annotations

import json

import pytest

import engine.job_pipeline as job_pipeline_module
import job_store
import utils
from engine.automation.dedupe import find_duplicate
from engine.automation.ingestion import adapt_and_ingest
from engine.automation.queue_actions import (
    approve_resume,
    approve_submit,
    list_awaiting_application_review,
    list_pending_approval,
    list_ready_to_submit,
    list_resume_approved,
    mark_ready_to_submit,
)
from engine.automation.radar import RawJobPosting
from engine.automation.scoring import score_job
from engine.automation.state_machine import WorkflowStatus, get_workflow_status
import engine.automation.tracking as tracking_module
from engine.automation.tracking import register_application
from engine.application.session import fill_application_form, run_application_prep
from engine.application.submit import submit_application
from engine.job_pipeline import JobPipeline
from job_store import job_path, load_job, write_json

_FORM_HTML = """
<html><body>
<form id="app-form">
  <label for="email">Email</label>
  <input type="email" id="email" name="email">

  <label for="linkedin">LinkedIn</label>
  <input type="text" id="linkedin" name="linkedin">

  <button type="submit" id="submit-btn">Submit Application</button>
</form>
<script>
document.getElementById('app-form').addEventListener('submit', function (e) {
  e.preventDefault();
  document.body.innerHTML = '<h1>Thank you for applying!</h1>';
});
</script>
</body></html>
"""


@pytest.fixture
def isolated_environment(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "data" / "jobs"
    jobs_dir.mkdir(parents=True)
    applications_path = tmp_path / "applications.json"
    applications_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(job_store, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(job_store, "ACTIVE_POINTER", jobs_dir / "active.json")
    monkeypatch.setattr(job_pipeline_module, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(job_pipeline_module, "ADAPTADOS_DIR", tmp_path / "adaptados")
    monkeypatch.setattr(job_pipeline_module, "GRAPH_CLEAN_PATH", tmp_path / "no-graph.json")
    monkeypatch.setattr(tracking_module, "APPLICATIONS_PATH", applications_path)

    def fake_adapt(master, jd, lang, api_key=None):
        return utils.AdaptedResume(
            name="Kevin Augusto Vieira", location="Curitiba, Brasil", phone="+55 41 90000-0000",
            email="kevin@example.com", linkedin="linkedin.com/in/kevin",
            summary=f"Perfil adequado para a vaga na {jd[:0] or 'Acme'}.",
            experience=[], skills=[], education=[], certifications=[], languages=[],
        )

    def fake_materials(master, jd, lang, api_key=None):
        return utils.JobMaterials(cover_letter="Carta para a Acme.", form_answers=[])

    monkeypatch.setattr(utils, "adapt_resume_with_llm", fake_adapt)
    monkeypatch.setattr(utils, "generate_job_materials", fake_materials)

    pipeline = JobPipeline()
    pipeline.master_resume = {}
    pipeline.graph_clean = {}
    return jobs_dir, applications_path, pipeline


def test_full_pipeline_walks_every_gate_and_registers_only_after_submit(
    isolated_environment, playwright_page
):
    jobs_dir, applications_path, pipeline = isolated_environment

    # --- Fase 2: a posting is discovered ---
    posting = RawJobPosting(
        company="Acme", title="Product Marketing Manager",
        url="https://boards.greenhouse.io/acme/jobs/1",
        description="Own GTM strategy for our AI governance product line.",
        location="Remote - Brazil", remote=True, source="greenhouse",
    )
    assert find_duplicate(
        url=posting.url, company=posting.company, role=posting.title,
        existing_jobs=[], existing_applications=[],
    ) is None  # genuinely new, nothing to dedupe against

    score = score_job(
        title=posting.title, description=posting.description,
        location=posting.location, remote=posting.remote,
    )
    assert score.passes_gate

    # --- Fase 3: ingestion (adapt + pipeline), ending at Gate #1 ---
    result = adapt_and_ingest(posting, score, master_resume={}, pipeline=pipeline, generate_pdfs=False)
    job_id = result["job_data"]["id"]
    on_disk = load_job(job_id)
    assert get_workflow_status(on_disk) == WorkflowStatus.AWAITING_RESUME_APPROVAL
    assert not (jobs_dir / "active.json").exists()  # never auto-activated
    assert json.loads(applications_path.read_text()) == []  # nothing tracked yet

    # --- Fase 4: Gate #1 — Aprovar currículo (via queue_actions, as Streamlit calls it) ---
    assert [j["id"] for j in list_pending_approval()] == [job_id]
    approve_resume(job_id)
    assert get_workflow_status(load_job(job_id)) == WorkflowStatus.RESUME_APPROVED
    assert [j["id"] for j in list_resume_approved()] == [job_id]

    # --- Fase 5: Application Prep Agent fills the real (local Chromium) form ---
    playwright_page.set_content(_FORM_HTML)
    job = load_job(job_id)
    session = run_application_prep(
        job, master_resume={}, page_factory=lambda: playwright_page, use_llm=False
    )
    write_json(job_path(job_id), job)
    assert get_workflow_status(load_job(job_id)) == WorkflowStatus.AWAITING_APPLICATION_REVIEW
    assert any(f.value == "kevin@example.com" for f in session.filled)
    assert [j["id"] for j in list_awaiting_application_review()] == [job_id]
    assert json.loads(applications_path.read_text()) == []  # still nothing tracked

    # --- Fase 4 (review UI)/5: human confirms the filled form looks right ---
    mark_ready_to_submit(job_id)
    assert get_workflow_status(load_job(job_id)) == WorkflowStatus.READY_TO_SUBMIT
    assert [j["id"] for j in list_ready_to_submit()] == [job_id]

    # --- Gate #2 — Aprovar envio (the plan's second, structural human gate) ---
    approve_submit(job_id)
    assert get_workflow_status(load_job(job_id)) == WorkflowStatus.SUBMIT_APPROVED
    assert json.loads(applications_path.read_text()) == []  # STILL nothing tracked — not submitted yet

    # --- Fase 6: submit agent re-fills (fresh page) then clicks Submit for real ---
    job = load_job(job_id)
    playwright_page.set_content(_FORM_HTML)  # simulate re-opening the same posting
    fill_application_form(playwright_page, job, master_resume={}, use_llm=False)
    submit_result = submit_application(job, page=playwright_page, wait_after_click_ms=200)
    write_json(job_path(job_id), job)

    assert submit_result.submitted is True
    assert get_workflow_status(load_job(job_id)) == WorkflowStatus.APPLIED

    # --- tracking: applications.json only gets an entry now, after real confirmation ---
    register_application(job, submitted_at="2026-08-31T12:00:00+00:00")
    applications = json.loads(applications_path.read_text())
    assert len(applications) == 1
    assert applications[0]["company"] == "Acme"
    assert applications[0]["source_job_id"] == job_id
