"""Tests for engine/application/session.py — the Fase 5 orchestrator. Uses a real
headless Chromium page (page.set_content, no network) as the `page_factory` result,
so these exercise actual DOM filling, not a mocked Playwright object."""
from __future__ import annotations

import pytest

from engine.application.session import (
    UnsupportedAtsError,
    fill_application_form,
    run_application_prep,
)
from engine.automation.state_machine import (
    InvalidTransitionError,
    WorkflowStatus,
    ensure_automation_block,
    get_workflow_status,
    transition,
)

_FORM_HTML = """
<html><body>
<form>
  <label for="email">Email</label>
  <input type="email" id="email" name="email">

  <label for="linkedin">LinkedIn</label>
  <input type="text" id="linkedin" name="linkedin">

  <label>
    Why are you interested in this company?
    <textarea name="why_interested"></textarea>
  </label>

  <label>
    Describe your obscure hobby involving glassblowing
    <textarea name="hobby"></textarea>
  </label>

  <fieldset>
    <legend>Are you willing to relocate?</legend>
    <input type="radio" name="relocate" value="yes" id="relocate_yes">
    <label for="relocate_yes">Yes</label>
    <input type="radio" name="relocate" value="no" id="relocate_no">
    <label for="relocate_no">No</label>
  </fieldset>

  <input type="checkbox" name="consent" id="consent">
  <label for="consent">I agree to the privacy policy</label>
</form>
</body></html>
"""

_RESUME = {
    "name": "Kevin Augusto Vieira", "email": "kevin@example.com", "phone": "+55 41 9999-0000",
    "linkedin": "linkedin.com/in/kevin", "location": "Curitiba, Brasil",
}
_MATERIALS = {
    "cover_letter": "Carta.",
    "form_answers": [
        {"question": "Why are you interested in this company?", "answer": "Porque admiro a missão."},
        {"question": "Are you willing to relocate?", "answer": "Yes"},
    ],
}
_MASTER_RESUME = {"work_experience": [], "technical_skills": {}}


def _job_at(status: WorkflowStatus, url="https://boards.greenhouse.io/acme/jobs/1"):
    job = {
        "id": "acme-role",
        "metadata": {"company_name": "Acme", "role_title": "Role", "url": url},
        "resume": {"pt": _RESUME},
        "materials": {"pt": _MATERIALS},
    }
    ensure_automation_block(job, source="radar:greenhouse")
    if status != WorkflowStatus.DISCOVERED:
        # Walk through the legal path to `status` rather than hand-editing the block.
        path = {
            WorkflowStatus.RESUME_APPROVED: [
                WorkflowStatus.QUALIFIED, WorkflowStatus.ADAPTING, WorkflowStatus.VALIDATING,
                WorkflowStatus.AWAITING_RESUME_APPROVAL, WorkflowStatus.RESUME_APPROVED,
            ],
            WorkflowStatus.AWAITING_RESUME_APPROVAL: [
                WorkflowStatus.QUALIFIED, WorkflowStatus.ADAPTING, WorkflowStatus.VALIDATING,
                WorkflowStatus.AWAITING_RESUME_APPROVAL,
            ],
        }[status]
        for step in path:
            transition(job, step)
    return job


def test_fill_application_form_resolves_all_tiers(playwright_page):
    playwright_page.set_content(_FORM_HTML)
    job = _job_at(WorkflowStatus.RESUME_APPROVED)

    session = fill_application_form(playwright_page, job, _MASTER_RESUME, lang="pt", use_llm=False)

    filled_by_label = {f.label: f for f in session.filled}
    assert "kevin@example.com" == playwright_page.eval_on_selector("#email", "el => el.value")
    assert "linkedin.com/in/kevin" == playwright_page.eval_on_selector("#linkedin", "el => el.value")
    assert playwright_page.eval_on_selector("#relocate_yes", "el => el.checked") is True

    human_labels = {f.label for f in session.human_required}
    assert any("glassblowing" in label for label in human_labels)
    assert any("privacy policy" in label.casefold() for label in human_labels)


def test_run_application_prep_requires_resume_approved_status(playwright_page):
    job = _job_at(WorkflowStatus.AWAITING_RESUME_APPROVAL)

    with pytest.raises(InvalidTransitionError):
        run_application_prep(
            job, _MASTER_RESUME, page_factory=lambda: playwright_page, use_llm=False
        )


def test_run_application_prep_rejects_unsupported_ats(playwright_page):
    job = _job_at(WorkflowStatus.RESUME_APPROVED, url="https://linkedin.com/jobs/view/12345")

    with pytest.raises(UnsupportedAtsError):
        run_application_prep(
            job, _MASTER_RESUME, page_factory=lambda: playwright_page, use_llm=False
        )
    # Rejecting before doing anything shouldn't leave the job stuck mid-transition.
    assert get_workflow_status(job) == WorkflowStatus.RESUME_APPROVED


def test_run_application_prep_reaches_awaiting_application_review(playwright_page):
    playwright_page.set_content(_FORM_HTML)
    job = _job_at(WorkflowStatus.RESUME_APPROVED)

    session = run_application_prep(
        job, _MASTER_RESUME, page_factory=lambda: playwright_page, use_llm=False
    )

    assert get_workflow_status(job) == WorkflowStatus.AWAITING_APPLICATION_REVIEW
    assert job["automation"]["application_session"]["job_id"] == "acme-role"
    assert len(session.filled) > 0
    assert len(session.human_required) > 0


def test_run_application_prep_moves_to_blocked_on_failure(playwright_page):
    job = _job_at(WorkflowStatus.RESUME_APPROVED)

    def _boom():
        raise RuntimeError("navigation timed out")

    with pytest.raises(RuntimeError):
        run_application_prep(job, _MASTER_RESUME, page_factory=_boom, use_llm=False)

    assert get_workflow_status(job) == WorkflowStatus.BLOCKED
    assert "navigation timed out" in job["automation"]["last_error"]
