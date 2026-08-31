"""The only module in this codebase that ever clicks a real Submit button.

Every earlier stage of the pipeline (radar, ingestion, form_parser, answer_engine,
session.py) is built so that reaching this point already required two separate,
structural human confirmations: RESUME_APPROVED (résumé/materials approved) and
SUBMIT_APPROVED (the human looked at the filled form and explicitly authorized
sending it — Gate #2 from the plan). This module trusts the state machine to have
enforced that and never re-derives permission any other way — it refuses to run at
all unless the job it's given is already SUBMIT_APPROVED.

It also never *assumes* success: clicking the button proves nothing by itself (a
validation error, a CAPTCHA, a network hiccup can all leave the form exactly where it
was), so `register_application()` (the write to applications.json) only happens after
`detect_submission_success()` finds a recognizable success indicator on the resulting
page. No indicator found -> the job goes to FAILED, not APPLIED, even though the
button was in fact clicked — an unconfirmed click is treated as a failure to avoid
ever recording an application that may not have actually gone through.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from engine.automation.state_machine import (
    InvalidTransitionError,
    WorkflowStatus,
    get_workflow_status,
    transition,
)

_SUBMIT_BUTTON_SELECTORS = ('button[type="submit"]', 'input[type="submit"]')
_SUBMIT_TEXT_KEYWORDS = (
    "submit application", "submit", "enviar candidatura", "apply now", "send application",
)
_SUCCESS_TEXT_KEYWORDS = (
    "application submitted", "thank you for applying", "thanks for applying",
    "your application has been received", "candidatura enviada", "successfully submitted",
    "application received",
)


@dataclass
class SubmitResult:
    job_id: str
    submitted: bool
    detected_success_text: Optional[str] = None
    final_url: Optional[str] = None
    error: Optional[str] = None


def find_submit_button(page):
    """Best-effort locator for the form's real submit control. Tries the standard
    input types first (unambiguous), then falls back to scanning buttons for common
    submit phrasing — ATS forms don't always mark their submit control with
    type="submit"."""
    for selector in _SUBMIT_BUTTON_SELECTORS:
        handle = page.query_selector(selector)
        if handle:
            return handle
    for handle in page.query_selector_all("button"):
        text = (handle.inner_text() or "").strip().casefold()
        if any(keyword in text for keyword in _SUBMIT_TEXT_KEYWORDS):
            return handle
    return None


def detect_submission_success(page) -> Optional[str]:
    """Heuristic check for a post-submit success indicator (returns the matched
    phrase, or None). Every ATS's "thank you" page reads differently, so a miss here
    doesn't prove the submission failed — it only means this can't confirm it, and
    the caller must never register an APPLIED status without a positive match."""
    try:
        body_text = (page.inner_text("body") or "").casefold()
    except Exception:
        return None
    for phrase in _SUCCESS_TEXT_KEYWORDS:
        if phrase in body_text:
            return phrase
    return None


def submit_application(
    job: Dict[str, Any],
    *,
    page,
    wait_after_click_ms: int = 4000,
) -> SubmitResult:
    """Click the real submit button and verify success against an already-filled
    `page` (the caller is responsible for having navigated to and filled the form —
    typically by re-running `engine.application.session.fill_application_form`
    immediately before this call, in the same browser session).

    Raises InvalidTransitionError, without touching the page, if `job` isn't
    SUBMIT_APPROVED. Otherwise always returns a SubmitResult and mutates `job`:
    APPLIED on confirmed success, FAILED (with the reason recorded) if the button
    can't be found or no success indicator is detected after clicking.
    """
    current_status = get_workflow_status(job)
    if current_status != WorkflowStatus.SUBMIT_APPROVED:
        raise InvalidTransitionError(
            "submit_application só pode rodar a partir de SUBMIT_APPROVED "
            f"(status atual: {current_status.value if current_status else 'sem automation'})."
        )

    button = find_submit_button(page)
    if button is None:
        transition(job, WorkflowStatus.FAILED, error="Botão de envio não encontrado no formulário.")
        return SubmitResult(job_id=job["id"], submitted=False, error="submit button not found")

    button.click()
    page.wait_for_timeout(wait_after_click_ms)

    success_phrase = detect_submission_success(page)
    final_url = page.url
    if success_phrase is None:
        transition(
            job, WorkflowStatus.FAILED,
            error="Clique em enviar não confirmado (nenhum indicador de sucesso detectado na página resultante).",
        )
        return SubmitResult(job_id=job["id"], submitted=False, final_url=final_url, error="success not confirmed")

    transition(job, WorkflowStatus.APPLIED)
    return SubmitResult(
        job_id=job["id"], submitted=True, detected_success_text=success_phrase, final_url=final_url
    )
