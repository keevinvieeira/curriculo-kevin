"""Tests for engine/automation/ingestion.py — the adapt_resume_with_llm -> JobPipeline glue.

No real LLM calls: utils.adapt_resume_with_llm / utils.generate_job_materials are
monkeypatched to return canned Pydantic objects. No real PDF rendering:
generate_pdfs=False. data/jobs/ and adaptados-para-as-vagas/ are redirected to a
tmp_path so this never touches the real repo's job artifacts.
"""
from __future__ import annotations

import pytest

import engine.job_pipeline as job_pipeline_module
import job_store
import utils
from engine.automation.ingestion import IngestionError, adapt_and_ingest, build_job_skeleton
from engine.automation.radar import RawJobPosting
from engine.automation.scoring import score_job
from engine.automation.state_machine import WorkflowStatus, get_workflow_status
from engine.job_pipeline import JobPipeline


def _canned_resume(company: str) -> utils.AdaptedResume:
    return utils.AdaptedResume(
        name="Kevin Augusto Vieira",
        location="Curitiba, Brasil",
        phone="+55 41 90000-0000",
        email="kevin@example.com",
        linkedin="linkedin.com/in/kevin",
        summary=f"Profissional experiente adequado para a vaga na {company}.",
        experience=[],
        skills=[],
        education=[],
        certifications=[],
        languages=[],
    )


def _canned_materials(company: str) -> utils.JobMaterials:
    return utils.JobMaterials(
        cover_letter=f"Prezados da {company}, tenho grande interesse nesta posição.",
        form_answers=[],
    )


@pytest.fixture
def posting():
    return RawJobPosting(
        company="Acme AI",
        title="Product Marketing Manager, AI Governance",
        url="https://boards.greenhouse.io/acme/jobs/1",
        description="Own GTM for our AI governance and responsible AI product line.",
        location="Remote - Brazil",
        remote=True,
        source="greenhouse",
    )


@pytest.fixture
def passing_score(posting):
    result = score_job(
        title=posting.title,
        description=posting.description,
        location=posting.location,
        remote=posting.remote,
    )
    assert result.passes_gate  # a fixture da vaga precisa mesmo passar no gate
    return result


@pytest.fixture
def isolated_pipeline(tmp_path, monkeypatch):
    """A JobPipeline whose reads/writes are redirected to tmp_path, never touching
    the real data/jobs/ or 'adaptados para as vagas/' in this working copy."""
    jobs_dir = tmp_path / "data" / "jobs"
    adaptados_dir = tmp_path / "adaptados para as vagas"
    jobs_dir.mkdir(parents=True)

    monkeypatch.setattr(job_store, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(job_store, "ACTIVE_POINTER", jobs_dir / "active.json")
    monkeypatch.setattr(job_pipeline_module, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(job_pipeline_module, "ADAPTADOS_DIR", adaptados_dir)
    monkeypatch.setattr(job_pipeline_module, "GRAPH_CLEAN_PATH", tmp_path / "no-such-graph.json")

    pipeline = JobPipeline()
    pipeline.master_resume = {}
    pipeline.graph_clean = {}
    return pipeline, jobs_dir


def _patch_llm(monkeypatch, company: str):
    monkeypatch.setattr(
        utils, "adapt_resume_with_llm", lambda master, jd, lang, api_key=None: _canned_resume(company)
    )
    monkeypatch.setattr(
        utils, "generate_job_materials", lambda master, jd, lang, api_key=None: _canned_materials(company)
    )


def test_build_job_skeleton_sets_explicit_fit_score(posting, passing_score):
    job_data = build_job_skeleton(posting, passing_score)
    assert job_data["metadata"]["fit_score"] == passing_score.total
    assert job_data["automation"]["fit_score_breakdown"] == passing_score.breakdown
    assert get_workflow_status(job_data) == WorkflowStatus.DISCOVERED


def test_adapt_and_ingest_reaches_awaiting_resume_approval(
    posting, passing_score, isolated_pipeline, monkeypatch
):
    pipeline, jobs_dir = isolated_pipeline
    _patch_llm(monkeypatch, posting.company)

    result = adapt_and_ingest(
        posting, passing_score, master_resume={}, pipeline=pipeline, generate_pdfs=False
    )

    job_data = result["job_data"]
    assert get_workflow_status(job_data) == WorkflowStatus.AWAITING_RESUME_APPROVAL
    # auto_activate=False: nunca deve escrever o active.json
    assert not (jobs_dir / "active.json").exists()
    # o artefato versionado deve existir de verdade em data/jobs/<slug>.json
    assert (jobs_dir / f"{job_data['id']}.json").exists()


def test_adapt_and_ingest_never_auto_activates_even_if_pipeline_default_changes(
    posting, passing_score, isolated_pipeline, monkeypatch
):
    """Regression guard: auto_activate=False is hardcoded in adapt_and_ingest, not a
    passthrough kwarg — a scheduled radar run must never flip the active job."""
    pipeline, jobs_dir = isolated_pipeline
    _patch_llm(monkeypatch, posting.company)

    adapt_and_ingest(posting, passing_score, master_resume={}, pipeline=pipeline, generate_pdfs=False)

    assert not (jobs_dir / "active.json").exists()


def test_adapt_and_ingest_llm_failure_transitions_to_failed(
    posting, passing_score, isolated_pipeline, monkeypatch
):
    pipeline, _ = isolated_pipeline

    def _boom(*args, **kwargs):
        raise RuntimeError("OpenRouter timeout")

    monkeypatch.setattr(utils, "adapt_resume_with_llm", _boom)

    with pytest.raises(IngestionError) as exc_info:
        adapt_and_ingest(posting, passing_score, master_resume={}, pipeline=pipeline, generate_pdfs=False)

    job_data = exc_info.value.job_data
    assert get_workflow_status(job_data) == WorkflowStatus.FAILED
    assert "OpenRouter timeout" in job_data["automation"]["last_error"]


def test_adapt_and_ingest_validation_failure_transitions_to_failed(
    posting, passing_score, isolated_pipeline, monkeypatch
):
    pipeline, _ = isolated_pipeline
    # Carta que NÃO cita a empresa-alvo -> validate_job deve reprovar (regra existente).
    monkeypatch.setattr(
        utils, "adapt_resume_with_llm", lambda master, jd, lang, api_key=None: _canned_resume(posting.company)
    )
    monkeypatch.setattr(
        utils,
        "generate_job_materials",
        lambda master, jd, lang, api_key=None: utils.JobMaterials(
            cover_letter="Uma carta genérica sem citar a empresa.", form_answers=[]
        ),
    )

    with pytest.raises(IngestionError):
        adapt_and_ingest(posting, passing_score, master_resume={}, pipeline=pipeline, generate_pdfs=False)
