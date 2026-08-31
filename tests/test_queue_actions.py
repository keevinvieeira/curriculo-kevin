"""Tests for engine/automation/queue_actions.py — the four actions behind the
Streamlit approval queue (Aprovar/Reprocessar/Descartar; Revisar is a direct call to
job_store.activate_job from app.py, not covered here)."""
from __future__ import annotations

import pytest

import engine.job_pipeline as job_pipeline_module
import job_store
import utils
from engine.automation.ingestion import IngestionError
from engine.automation.queue_actions import (
    approve_resume,
    discard_job,
    list_pending_approval,
    reprocess_job,
)
from engine.automation.state_machine import WorkflowStatus, get_workflow_status
from engine.job_pipeline import JobPipeline
from job_store import job_path, write_json


@pytest.fixture
def isolated_pipeline(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "data" / "jobs"
    jobs_dir.mkdir(parents=True)
    monkeypatch.setattr(job_store, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(job_store, "ACTIVE_POINTER", jobs_dir / "active.json")
    monkeypatch.setattr(job_pipeline_module, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(job_pipeline_module, "ADAPTADOS_DIR", tmp_path / "adaptados")
    monkeypatch.setattr(job_pipeline_module, "GRAPH_CLEAN_PATH", tmp_path / "no-graph.json")
    pipeline = JobPipeline()
    pipeline.master_resume = {}
    pipeline.graph_clean = {}
    return pipeline, jobs_dir


def _seeded_job(job_id="acme-pmm", status=WorkflowStatus.AWAITING_RESUME_APPROVAL, with_description=True):
    job = {
        "id": job_id,
        "metadata": {
            "company_name": "Acme",
            "role_title": "Product Marketing Manager",
            "url": "https://boards.greenhouse.io/acme/jobs/1",
            "fit_score": 85,
            "document_language": "pt",
            "location": "Remote - Brazil",
            "work_model": "Remoto",
            "salary_expectation": "Não informada",
            "source_files": ["master_resume.json"],
            "good_points": [],
            "improvement_points": [],
        },
        "triage": {"decision": "adapt", "notes": "teste"},
        "resume": {
            "pt": {
                "name": "Kevin", "location": "Curitiba", "phone": "x", "email": "k@example.com",
                "linkedin": "li", "summary": "Resumo para a Acme.", "experience": [], "skills": [],
                "education": [], "certifications": [], "languages": [],
            },
            "en": {
                "name": "Kevin", "location": "Curitiba", "phone": "x", "email": "k@example.com",
                "linkedin": "li", "summary": "Summary for Acme.", "experience": [], "skills": [],
                "education": [], "certifications": [], "languages": [],
            },
        },
        "materials": {
            "pt": {"cover_letter": "Carta para a Acme.", "form_answers": []},
            "en": {"cover_letter": "Letter for Acme.", "form_answers": []},
        },
        "evidence": {"skills": {"pt": [], "en": []}},
        "automation": {
            "source": "radar:greenhouse",
            "discovered_at": "2026-01-01T00:00:00+00:00",
            "workflow_status": status.value,
            "fit_score_breakdown": {"category_match": 50, "location": 25, "salary": 0, "recency": 10},
            "resume_approved_at": None,
            "application_started_at": None,
            "application_ready_at": None,
            "submit_approved_at": None,
            "submitted_at": None,
            "last_error": None,
        },
    }
    if with_description:
        job["automation"]["source_description"] = "Own GTM for our AI governance product line."
    return job


def test_list_pending_approval_only_returns_awaiting_resume_approval(isolated_pipeline):
    _, jobs_dir = isolated_pipeline
    pending = _seeded_job("acme-pmm", WorkflowStatus.AWAITING_RESUME_APPROVAL)
    approved = _seeded_job("beta-pmm", WorkflowStatus.RESUME_APPROVED)
    write_json(job_path("acme-pmm"), pending)
    write_json(job_path("beta-pmm"), approved)

    result = list_pending_approval()

    assert [job["id"] for job in result] == ["acme-pmm"]


def test_approve_resume_transitions_and_persists(isolated_pipeline):
    _, jobs_dir = isolated_pipeline
    write_json(job_path("acme-pmm"), _seeded_job("acme-pmm", WorkflowStatus.AWAITING_RESUME_APPROVAL))

    approve_resume("acme-pmm")

    on_disk = job_store.load_job("acme-pmm")
    assert get_workflow_status(on_disk) == WorkflowStatus.RESUME_APPROVED
    assert on_disk["automation"]["resume_approved_at"] is not None


def test_discard_job_transitions_and_persists(isolated_pipeline):
    _, jobs_dir = isolated_pipeline
    write_json(job_path("acme-pmm"), _seeded_job("acme-pmm", WorkflowStatus.AWAITING_RESUME_APPROVAL))

    discard_job("acme-pmm")

    on_disk = job_store.load_job("acme-pmm")
    assert get_workflow_status(on_disk) == WorkflowStatus.DISCARDED


def test_reprocess_job_without_saved_description_raises_value_error(isolated_pipeline):
    _, jobs_dir = isolated_pipeline
    write_json(
        job_path("acme-pmm"),
        _seeded_job("acme-pmm", WorkflowStatus.AWAITING_RESUME_APPROVAL, with_description=False),
    )

    with pytest.raises(ValueError):
        reprocess_job("acme-pmm", master_resume={})


def test_reprocess_job_rejects_wrong_status(isolated_pipeline):
    _, jobs_dir = isolated_pipeline
    write_json(job_path("acme-pmm"), _seeded_job("acme-pmm", WorkflowStatus.RESUME_APPROVED))

    with pytest.raises(Exception):
        reprocess_job("acme-pmm", master_resume={})


def test_reprocess_job_reruns_adaptation_and_reaches_awaiting_approval(isolated_pipeline, monkeypatch):
    pipeline, jobs_dir = isolated_pipeline
    write_json(job_path("acme-pmm"), _seeded_job("acme-pmm", WorkflowStatus.AWAITING_RESUME_APPROVAL))

    def fake_adapt(master, jd, lang, api_key=None):
        return utils.AdaptedResume(
            name="Kevin", location="Curitiba", phone="x", email="k@example.com", linkedin="li",
            summary="Resumo atualizado.", experience=[], skills=[], education=[],
            certifications=[], languages=[],
        )

    def fake_materials(master, jd, lang, api_key=None):
        return utils.JobMaterials(cover_letter="Carta atualizada para a Acme.", form_answers=[])

    monkeypatch.setattr(utils, "adapt_resume_with_llm", fake_adapt)
    monkeypatch.setattr(utils, "generate_job_materials", fake_materials)

    job_data = reprocess_job("acme-pmm", master_resume={}, pipeline=pipeline, generate_pdfs=False)

    assert get_workflow_status(job_data) == WorkflowStatus.AWAITING_RESUME_APPROVAL
    on_disk = job_store.load_job(job_data["id"])
    assert get_workflow_status(on_disk) == WorkflowStatus.AWAITING_RESUME_APPROVAL
    assert on_disk["resume"]["pt"]["summary"] == "Resumo atualizado."


def test_reprocess_job_llm_failure_raises_ingestion_error(isolated_pipeline, monkeypatch):
    pipeline, jobs_dir = isolated_pipeline
    write_json(job_path("acme-pmm"), _seeded_job("acme-pmm", WorkflowStatus.FAILED))

    def _boom(*args, **kwargs):
        raise RuntimeError("OpenRouter timeout")

    monkeypatch.setattr(utils, "adapt_resume_with_llm", _boom)

    with pytest.raises(IngestionError):
        reprocess_job("acme-pmm", master_resume={}, pipeline=pipeline, generate_pdfs=False)
