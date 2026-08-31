"""Glue between a discovered posting and the existing Career OS pipeline.

This is the piece the original automation plan glossed over: `JobPipeline` does NOT
adapt a résumé — it only validates/saves/activates/exports PDFs for a job_data dict
that already has `resume.pt/en` and `materials.pt/en` fully written. The actual
adaptation is `utils.adapt_resume_with_llm()` / `utils.generate_job_materials()`
(now backed by OpenRouter, see llm_client.py). This module is the explicit sequence:

    RawJobPosting + ScoreResult
        -> job_data metadata/triage skeleton
        -> ensure_automation_block() + transition(QUALIFIED) + transition(ADAPTING)
        -> adapt_resume_with_llm(pt), adapt_resume_with_llm(en)
        -> generate_job_materials(pt), generate_job_materials(en)
        -> transition(VALIDATING)
        -> JobPipeline.process_job_artifact(job_data, auto_activate=False)
        -> transition(AWAITING_RESUME_APPROVAL)  [or FAILED, with the error recorded]

`fit_score` is always taken from the ScoreResult computed by scoring.py and set
explicitly in metadata *before* calling the pipeline — never left for
JobPipeline's own `metadata.setdefault("fit_score", 95)` to kick in.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import utils
from engine.automation.dedupe import find_duplicate
from engine.automation.radar import RawJobPosting
from engine.automation.scoring import ScoreResult
from engine.automation.state_machine import (
    WorkflowStatus,
    ensure_automation_block,
    transition,
)
from engine.job_pipeline import JobPipeline
from job_store import job_path, slugify, write_json


class IngestionError(Exception):
    """Raised when adaptation or pipeline processing fails for a posting.

    The job_data (with workflow_status == FAILED and last_error set) is attached so
    the caller can inspect/log/retry it rather than losing the partial state.
    """

    def __init__(self, message: str, job_data: Dict[str, Any]):
        super().__init__(message)
        self.job_data = job_data


def build_job_skeleton(posting: RawJobPosting, score: ScoreResult) -> Dict[str, Any]:
    """Build the metadata/triage skeleton for a job_data dict — everything except the
    LLM-generated resume/materials, which get filled in by adapt_and_ingest()."""
    slug = slugify(f"{posting.company}-{posting.title}")
    job_data: Dict[str, Any] = {
        "id": slug,
        "metadata": {
            "company_name": posting.company,
            "role_title": posting.title,
            "url": posting.url,
            "fit_score": score.total,  # explícito, nunca via default do pipeline
            "document_language": "pt",
            "location": posting.location,
            "work_model": "Remoto" if posting.remote else (posting.employment_type or "Não informado"),
            "employment_type": posting.employment_type or "Não informado",
            "salary_expectation": posting.salary_range or "Não informada",
            "source_files": ["master_resume.json"],
            "good_points": [],
            "improvement_points": [],
        },
        "triage": {
            "decision": "adapt",
            "notes": (
                f"Descoberta automática via radar ({posting.source}). "
                f"Score determinístico: {score.total}/100 "
                f"(categorias: {', '.join(score.matched_categories) or 'nenhuma'})."
            ),
        },
        "evidence": {"skills": {"pt": [], "en": []}},
    }
    ensure_automation_block(job_data, source=f"radar:{posting.source}")
    job_data["automation"]["fit_score_breakdown"] = score.breakdown
    # Kept so the approval queue's "Reprocessar" action (Fase 4) can re-run adaptation
    # later without re-fetching the posting — the JD text itself isn't part of the
    # validate_job()-checked schema, so storing it here is additive/safe.
    job_data["automation"]["source_description"] = posting.description
    return job_data


def adapt_and_ingest(
    posting: RawJobPosting,
    score: ScoreResult,
    master_resume: Dict[str, Any],
    *,
    pipeline: Optional[JobPipeline] = None,
    generate_pdfs: bool = True,
) -> Dict[str, Any]:
    """Run one posting through adaptation + the existing pipeline, up to the first
    human gate (AWAITING_RESUME_APPROVAL). Never activates the job in Streamlit
    (auto_activate=False is hardcoded here, not a caller-adjustable option) — a
    scheduled radar run must never change what `data/jobs/active.json` points to.

    Raises IngestionError (with the partial job_data attached, workflow_status set to
    FAILED) if adaptation or pipeline validation fails. Never raises for a job that
    simply doesn't meet the fit_score gate — callers should check `score.passes_gate`
    before calling this at all; this function assumes that check already happened.
    """
    job_data = build_job_skeleton(posting, score)
    transition(job_data, WorkflowStatus.QUALIFIED)
    transition(job_data, WorkflowStatus.ADAPTING)

    try:
        job_data["resume"] = {
            "pt": utils.adapt_resume_with_llm(master_resume, posting.description, "pt").model_dump(),
            "en": utils.adapt_resume_with_llm(master_resume, posting.description, "en").model_dump(),
        }
        job_data["materials"] = {
            "pt": utils.generate_job_materials(master_resume, posting.description, "pt").model_dump(),
            "en": utils.generate_job_materials(master_resume, posting.description, "en").model_dump(),
        }
    except Exception as exc:  # noqa: BLE001 - qualquer falha de LLM vira FAILED, nunca propaga crua
        transition(job_data, WorkflowStatus.FAILED, error=f"Falha na adaptação via LLM: {exc}")
        raise IngestionError(str(exc), job_data) from exc

    transition(job_data, WorkflowStatus.VALIDATING)

    active_pipeline = pipeline or JobPipeline()
    try:
        result = active_pipeline.process_job_artifact(
            job_data, generate_pdfs=generate_pdfs, auto_activate=False
        )
    except Exception as exc:  # noqa: BLE001 - inclui ValueError de validate_job
        transition(job_data, WorkflowStatus.FAILED, error=f"Falha no pipeline/validação: {exc}")
        raise IngestionError(str(exc), job_data) from exc

    transition(job_data, WorkflowStatus.AWAITING_RESUME_APPROVAL)
    # `process_job_artifact` already wrote job_data to disk, but at that point
    # workflow_status was still VALIDATING — the transition above only mutated the
    # in-memory dict. Re-persist so data/jobs/<slug>.json reflects the real final
    # status; otherwise the Streamlit approval queue (which reads straight from disk)
    # would never see this job as AWAITING_RESUME_APPROVAL.
    write_json(job_path(job_data["id"]), job_data)
    result["job_data"] = job_data
    return result


def is_duplicate_posting(
    posting: RawJobPosting, existing_jobs: list, existing_applications: list
) -> Optional[str]:
    """Thin wrapper around dedupe.find_duplicate() using a RawJobPosting's fields."""
    return find_duplicate(
        url=posting.url,
        company=posting.company,
        role=posting.title,
        existing_jobs=existing_jobs,
        existing_applications=existing_applications,
    )
