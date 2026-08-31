"""Actions behind the Streamlit approval queue (Fase 4 / Sprint C).

This is the only place the queue UI (`app.py`) talks to the automation layer — it
never touches `data/jobs/*.json` or the state machine directly, so the same four
actions (Revisar/Aprovar/Reprocessar/Descartar) stay testable without Streamlit.

"Revisar" isn't implemented here: it's a direct call to the existing
`job_store.activate_job()` from `app.py`, per the plan — no new code needed for that
one, and duplicating a thin wrapper around it would just be indirection.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.automation.ingestion import IngestionError, adapt_and_ingest
from engine.automation.radar import RawJobPosting
from engine.automation.scoring import score_job
from engine.automation.state_machine import (
    InvalidTransitionError,
    WorkflowStatus,
    get_workflow_status,
    transition,
)
from engine.job_pipeline import JobPipeline
from job_store import job_path, list_jobs, load_job, write_json


def list_pending_approval() -> List[Dict[str, Any]]:
    """Every job artifact currently sitting at the first human gate, newest-first."""
    pending = [
        job for job in list_jobs()
        if get_workflow_status(job) == WorkflowStatus.AWAITING_RESUME_APPROVAL
    ]
    pending.sort(key=lambda job: job.get("automation", {}).get("discovered_at") or "", reverse=True)
    return pending


def list_resume_approved() -> List[Dict[str, Any]]:
    """Jobs approved for the Application Prep Agent to pick up (Fase 5) — not yet
    run through it. `scripts/run_application_agent.py` is what actually consumes
    this, not the Streamlit queue directly (a real browser run doesn't belong inside
    a web request/response cycle)."""
    return [job for job in list_jobs() if get_workflow_status(job) == WorkflowStatus.RESUME_APPROVED]


def list_awaiting_application_review() -> List[Dict[str, Any]]:
    """Jobs the Application Prep Agent already ran on — the second human gate's
    review screen (fields filled + gaps left for the human) reads this."""
    return [
        job for job in list_jobs()
        if get_workflow_status(job) == WorkflowStatus.AWAITING_APPLICATION_REVIEW
    ]


def mark_ready_to_submit(job_id: str) -> Dict[str, Any]:
    """AWAITING_APPLICATION_REVIEW -> READY_TO_SUBMIT: the human confirms the filled
    form (and any fields they completed by hand) looks correct. This is still not
    permission to submit — that's the separate SUBMIT_APPROVED gate (Fase 6)."""
    job = load_job(job_id)
    transition(job, WorkflowStatus.READY_TO_SUBMIT)
    write_json(job_path(job_id), job)
    return job


def approve_resume(job_id: str) -> Dict[str, Any]:
    """AWAITING_RESUME_APPROVAL -> RESUME_APPROVED. Never activates the job in
    Streamlit — approving the résumé and previewing/activating it are separate
    actions ("Aprovar" vs "Revisar"), per the plan."""
    job = load_job(job_id)
    transition(job, WorkflowStatus.RESUME_APPROVED)
    write_json(job_path(job_id), job)
    return job


def discard_job(job_id: str) -> Dict[str, Any]:
    """Move a job out of the queue permanently (DISCARDED is terminal)."""
    job = load_job(job_id)
    transition(job, WorkflowStatus.DISCARDED)
    write_json(job_path(job_id), job)
    return job


def reprocess_job(
    job_id: str,
    master_resume: Dict[str, Any],
    *,
    pipeline: Optional[JobPipeline] = None,
    generate_pdfs: bool = True,
) -> Dict[str, Any]:
    """Re-run adaptation from scratch for a job already sitting in the queue (or one
    that FAILED) using the original posting text saved by `build_job_skeleton()`.

    Raises ValueError if the job predates this field (nothing to reprocess from) or
    InvalidTransitionError if it isn't in a state reprocessing makes sense for.
    Raises IngestionError (propagated from adapt_and_ingest) if the re-adaptation
    itself fails — the queue UI is expected to surface that message and leave the
    job at FAILED, exactly like a first-time ingestion failure.
    """
    job = load_job(job_id)
    current_status = get_workflow_status(job)
    if current_status not in (WorkflowStatus.AWAITING_RESUME_APPROVAL, WorkflowStatus.FAILED):
        raise InvalidTransitionError(
            f"Reprocessar só é permitido a partir de AWAITING_RESUME_APPROVAL ou FAILED "
            f"(status atual: {current_status.value if current_status else 'sem automation'})."
        )

    automation = job.get("automation", {})
    description = automation.get("source_description")
    if not description:
        raise ValueError(
            f"Job '{job_id}' não tem a descrição original da vaga salva "
            "(automation.source_description) — não é possível reprocessar automaticamente. "
            "Foi criado antes desse campo existir, ou fora do fluxo do radar."
        )

    metadata = job.get("metadata", {})
    posting = RawJobPosting(
        company=metadata.get("company_name", ""),
        title=metadata.get("role_title", ""),
        url=metadata.get("url", ""),
        description=description,
        location=metadata.get("location", ""),
        remote=str(metadata.get("work_model", "")).casefold().startswith("remot"),
        source=(automation.get("source") or "radar:manual").split(":")[-1],
    )
    score = score_job(
        title=posting.title,
        description=posting.description,
        location=posting.location,
        remote=posting.remote,
    )

    result = adapt_and_ingest(
        posting, score, master_resume, pipeline=pipeline, generate_pdfs=generate_pdfs
    )
    return result["job_data"]
