"""Explicit state machine for the automation layer added on top of the Career OS.

Every vaga (job artifact, `data/jobs/<slug>.json`) that goes through the automated
radar/adaptation/application flow carries a `job["automation"]` block whose
`workflow_status` is one of the `WorkflowStatus` values below. Transitions between
statuses are validated explicitly against `TRANSITIONS` — nothing infers a job's
stage from which files happen to exist on disk (that was the original plan's own
diagnosis of what to avoid).

This module knows nothing about *how* a transition happens (calling Gemini/OpenRouter,
running Playwright, etc.) — it only enforces which transitions are legal and keeps the
`automation` block's timestamps consistent. Callers (radar.py, ingestion.py, the
Streamlit approval queue, the Application Prep Agent) call `transition()` after doing
the actual work.

Jobs created before this sprint (or created manually, outside the automation flow)
simply have no `automation` key — `get_workflow_status()` returns None for those, and
`job_store.validate_job` is untouched, so they remain valid without any changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Union


class WorkflowStatus(str, Enum):
    # Caminho principal
    DISCOVERED = "DISCOVERED"
    QUALIFIED = "QUALIFIED"
    ADAPTING = "ADAPTING"
    VALIDATING = "VALIDATING"
    AWAITING_RESUME_APPROVAL = "AWAITING_RESUME_APPROVAL"
    RESUME_APPROVED = "RESUME_APPROVED"
    APPLICATION_PREPARING = "APPLICATION_PREPARING"
    AWAITING_APPLICATION_REVIEW = "AWAITING_APPLICATION_REVIEW"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    SUBMIT_APPROVED = "SUBMIT_APPROVED"
    APPLIED = "APPLIED"

    # Estados laterais
    HOLD = "HOLD"
    DISCARDED = "DISCARDED"
    EXPIRED = "EXPIRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


StatusLike = Union[WorkflowStatus, str]

# Estados a partir dos quais um HOLD ou FAILED pode ser retomado de volta.
_RESUMABLE_ACTIVE_STATES: FrozenSet[WorkflowStatus] = frozenset(
    {
        WorkflowStatus.DISCOVERED,
        WorkflowStatus.QUALIFIED,
        WorkflowStatus.AWAITING_RESUME_APPROVAL,
        WorkflowStatus.RESUME_APPROVED,
        WorkflowStatus.READY_TO_SUBMIT,
    }
)

# Tabela explícita de transições válidas. Nunca inferida por arquivos em disco.
TRANSITIONS: Dict[WorkflowStatus, FrozenSet[WorkflowStatus]] = {
    WorkflowStatus.DISCOVERED: frozenset(
        {WorkflowStatus.QUALIFIED, WorkflowStatus.DISCARDED, WorkflowStatus.HOLD, WorkflowStatus.EXPIRED}
    ),
    WorkflowStatus.QUALIFIED: frozenset(
        {WorkflowStatus.ADAPTING, WorkflowStatus.DISCARDED, WorkflowStatus.HOLD, WorkflowStatus.EXPIRED}
    ),
    WorkflowStatus.ADAPTING: frozenset({WorkflowStatus.VALIDATING, WorkflowStatus.FAILED}),
    WorkflowStatus.VALIDATING: frozenset(
        {WorkflowStatus.AWAITING_RESUME_APPROVAL, WorkflowStatus.FAILED}
    ),
    WorkflowStatus.AWAITING_RESUME_APPROVAL: frozenset(
        {
            WorkflowStatus.RESUME_APPROVED,
            WorkflowStatus.ADAPTING,  # "Reprocessar" na fila de aprovação
            WorkflowStatus.DISCARDED,
            WorkflowStatus.HOLD,
        }
    ),
    WorkflowStatus.RESUME_APPROVED: frozenset(
        {WorkflowStatus.APPLICATION_PREPARING, WorkflowStatus.DISCARDED, WorkflowStatus.HOLD}
    ),
    WorkflowStatus.APPLICATION_PREPARING: frozenset(
        {WorkflowStatus.AWAITING_APPLICATION_REVIEW, WorkflowStatus.FAILED, WorkflowStatus.BLOCKED}
    ),
    WorkflowStatus.AWAITING_APPLICATION_REVIEW: frozenset(
        {
            WorkflowStatus.READY_TO_SUBMIT,
            WorkflowStatus.APPLICATION_PREPARING,  # revisar de novo / tentar outra vez
            WorkflowStatus.DISCARDED,
        }
    ),
    WorkflowStatus.READY_TO_SUBMIT: frozenset(
        {WorkflowStatus.SUBMIT_APPROVED, WorkflowStatus.DISCARDED, WorkflowStatus.HOLD}
    ),
    WorkflowStatus.SUBMIT_APPROVED: frozenset({WorkflowStatus.APPLIED, WorkflowStatus.FAILED}),
    # Terminais — nenhuma transição sai daqui.
    WorkflowStatus.APPLIED: frozenset(),
    WorkflowStatus.DISCARDED: frozenset(),
    WorkflowStatus.EXPIRED: frozenset(),
    # Estados laterais: retomam para um estado ativo específico, ou saem para DISCARDED.
    WorkflowStatus.HOLD: _RESUMABLE_ACTIVE_STATES | {WorkflowStatus.DISCARDED},
    WorkflowStatus.BLOCKED: frozenset({WorkflowStatus.HOLD, WorkflowStatus.DISCARDED}),
    WorkflowStatus.FAILED: frozenset(
        {
            WorkflowStatus.ADAPTING,
            WorkflowStatus.VALIDATING,
            WorkflowStatus.APPLICATION_PREPARING,
            WorkflowStatus.SUBMIT_APPROVED,
            WorkflowStatus.DISCARDED,
        }
    ),
}

# Quando o job entra num destes estados, o timestamp correspondente é preenchido.
_STATUS_TIMESTAMP_FIELD: Dict[WorkflowStatus, str] = {
    WorkflowStatus.RESUME_APPROVED: "resume_approved_at",
    WorkflowStatus.APPLICATION_PREPARING: "application_started_at",
    WorkflowStatus.READY_TO_SUBMIT: "application_ready_at",
    WorkflowStatus.SUBMIT_APPROVED: "submit_approved_at",
    WorkflowStatus.APPLIED: "submitted_at",
}


class InvalidTransitionError(ValueError):
    """Raised when a transition isn't allowed by TRANSITIONS."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce(status: StatusLike) -> WorkflowStatus:
    if isinstance(status, WorkflowStatus):
        return status
    try:
        return WorkflowStatus(status)
    except ValueError as exc:
        valid = ", ".join(s.value for s in WorkflowStatus)
        raise InvalidTransitionError(f"Status desconhecido: {status!r}. Válidos: {valid}") from exc


def get_workflow_status(job: Dict[str, Any]) -> Optional[WorkflowStatus]:
    """Return the job's current WorkflowStatus, or None if it has no `automation` block
    (i.e. it's a legacy/manually-managed job, outside the automation state machine)."""
    automation = job.get("automation")
    if not automation or not automation.get("workflow_status"):
        return None
    return _coerce(automation["workflow_status"])


def ensure_automation_block(
    job: Dict[str, Any], *, source: str = "manual", now: Optional[str] = None
) -> Dict[str, Any]:
    """Idempotently make sure `job["automation"]` exists, defaulting to DISCOVERED.

    Never overwrites an existing automation block — safe to call repeatedly. Jobs that
    were never touched by the automation layer, and on which this is never called,
    keep no `automation` key at all and remain fully valid for `job_store.validate_job`.
    """
    if "automation" in job and job["automation"]:
        return job
    job["automation"] = {
        "source": source,
        "discovered_at": now or _now_iso(),
        "workflow_status": WorkflowStatus.DISCOVERED.value,
        "fit_score_breakdown": None,
        "resume_approved_at": None,
        "application_started_at": None,
        "application_ready_at": None,
        "submit_approved_at": None,
        "submitted_at": None,
        "last_error": None,
    }
    return job


def transition(
    job: Dict[str, Any],
    new_status: StatusLike,
    *,
    now: Optional[str] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Move `job` to `new_status`, validating the transition and stamping timestamps.

    Raises InvalidTransitionError if the job has no automation block yet (call
    ensure_automation_block first) or if the transition isn't allowed from the
    current status. Mutates and returns `job` for convenience.
    """
    current = get_workflow_status(job)
    if current is None:
        raise InvalidTransitionError(
            "Job não tem bloco 'automation' — chame ensure_automation_block() antes de "
            "fazer a primeira transição."
        )
    target = _coerce(new_status)
    allowed = TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        allowed_names = ", ".join(s.value for s in sorted(allowed, key=lambda s: s.value)) or "(nenhum)"
        raise InvalidTransitionError(
            f"Transição inválida: {current.value} -> {target.value}. "
            f"Permitidas a partir de {current.value}: {allowed_names}."
        )

    job["automation"]["workflow_status"] = target.value

    timestamp_field = _STATUS_TIMESTAMP_FIELD.get(target)
    if timestamp_field:
        job["automation"][timestamp_field] = now or _now_iso()

    if target == WorkflowStatus.FAILED:
        job["automation"]["last_error"] = error
    elif target not in (WorkflowStatus.HOLD, WorkflowStatus.BLOCKED):
        # Sair de um estado de erro para um estado de progresso normal limpa o erro
        # anterior; HOLD/BLOCKED preservam o último erro para contexto de quem for revisar.
        job["automation"]["last_error"] = None

    return job
