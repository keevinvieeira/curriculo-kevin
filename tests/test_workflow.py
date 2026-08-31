"""Tests for engine/automation/workflow.py — the per-cycle orchestrator + cost cap."""
from __future__ import annotations

import pytest

import engine.job_pipeline as job_pipeline_module
import job_store
import utils
from engine.automation.radar import CustomSource, RawJobPosting
from engine.automation.workflow import run_automation_cycle
from engine.job_pipeline import JobPipeline


def _posting(company: str, category_hint: str = "Product Marketing GTM AI Governance") -> RawJobPosting:
    return RawJobPosting(
        company=company,
        title=f"{category_hint} Lead",
        url=f"https://boards.greenhouse.io/{company.lower()}/jobs/1",
        description=f"Own {category_hint} strategy, Trust & Safety and Responsible AI.",
        location="Remote - Brazil",
        remote=True,
        source="greenhouse",
    )


def _irrelevant_posting(company: str) -> RawJobPosting:
    return RawJobPosting(
        company=company,
        title="Warehouse Forklift Operator",
        url=f"https://boards.greenhouse.io/{company.lower()}/jobs/9",
        description="Operate forklifts in our distribution center.",
        location="Ohio, USA",
        remote=False,
        source="greenhouse",
    )


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


def _patch_llm(monkeypatch):
    def fake_adapt(master, jd, lang, api_key=None):
        return utils.AdaptedResume(
            name="Kevin",
            location="Curitiba",
            phone="x",
            email="k@example.com",
            linkedin="li",
            summary="Resumo.",
            experience=[],
            skills=[],
            education=[],
            certifications=[],
            languages=[],
        )

    def fake_materials(master, jd, lang, api_key=None):
        # cover_letter genérico não citando empresa seria reprovado — então incluímos
        # um placeholder que o teste substitui por-vaga quando precisa ser mais realista.
        return utils.JobMaterials(cover_letter="Carta para " + jd[:0] or "Carta.", form_answers=[])

    monkeypatch.setattr(utils, "adapt_resume_with_llm", fake_adapt)
    monkeypatch.setattr(utils, "generate_job_materials", fake_materials)


def test_cycle_skips_duplicates_and_below_gate_postings(isolated_pipeline, monkeypatch):
    pipeline, _ = isolated_pipeline
    _patch_llm(monkeypatch)
    # Sobrescreve generate_job_materials para citar a empresa (regra de validate_job).
    monkeypatch.setattr(
        utils,
        "generate_job_materials",
        lambda master, jd, lang, api_key=None: utils.JobMaterials(
            cover_letter="Carta para Acme, Beta e Gamma.", form_answers=[]
        ),
    )

    good_posting = _posting("Acme")
    irrelevant_posting = _irrelevant_posting("Beta")
    existing_jobs = [
        {
            "id": "gamma-existing",
            "metadata": {
                "url": "https://boards.greenhouse.io/gamma/jobs/1",
                "company_name": "Gamma",
                "role_title": "Product Marketing GTM AI Governance Lead",
            },
        }
    ]
    duplicate_posting = _posting("Gamma")  # mesma empresa/cargo do existing_jobs acima

    source = CustomSource("test", lambda: [good_posting, irrelevant_posting, duplicate_posting])

    report = run_automation_cycle(
        [source],
        master_resume={},
        existing_jobs=existing_jobs,
        existing_applications=[],
        pipeline=pipeline,
        generate_pdfs=False,
    )

    assert report.discovered == 3
    assert report.duplicates_skipped == 1
    assert report.below_gate_skipped == 1
    assert report.adapted == ["acme-product-marketing-gtm-ai-governance-lead"]
    assert report.failed == []


def test_cycle_respects_max_jobs_per_cycle_cap(isolated_pipeline, monkeypatch):
    pipeline, _ = isolated_pipeline
    _patch_llm(monkeypatch)
    monkeypatch.setattr(
        utils,
        "generate_job_materials",
        lambda master, jd, lang, api_key=None: utils.JobMaterials(
            cover_letter="Carta para Acme, Beta e Gamma.", form_answers=[]
        ),
    )

    postings = [_posting("Acme"), _posting("Beta"), _posting("Gamma")]
    source = CustomSource("test", lambda: postings)

    report = run_automation_cycle(
        [source],
        master_resume={},
        existing_jobs=[],
        existing_applications=[],
        max_jobs_per_cycle=1,
        pipeline=pipeline,
        generate_pdfs=False,
    )

    assert report.discovered == 3
    assert len(report.adapted) == 1
    assert report.deferred == 2


def test_cycle_records_source_errors_without_crashing(isolated_pipeline):
    pipeline, _ = isolated_pipeline

    def _boom():
        raise RuntimeError("board API down")

    source = CustomSource("flaky", _boom)

    report = run_automation_cycle(
        [source],
        master_resume={},
        existing_jobs=[],
        existing_applications=[],
        pipeline=pipeline,
        generate_pdfs=False,
    )

    assert report.discovered == 0
    assert report.source_errors == [{"source": "flaky", "error": "board API down"}]
