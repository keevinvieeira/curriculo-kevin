"""Tests for engine/application/submit.py — driven against a real headless Chromium
page (page.set_content, no network), including an actual button click and DOM
mutation, not a mocked Playwright object."""
from __future__ import annotations

import pytest

from engine.application.submit import detect_submission_success, find_submit_button, submit_application
from engine.automation.state_machine import (
    InvalidTransitionError,
    WorkflowStatus,
    ensure_automation_block,
    get_workflow_status,
    transition,
)

_FORM_WITH_SUCCESS_HTML = """
<html><body>
<form id="app-form">
  <input type="text" name="full_name">
  <button type="submit" id="submit-btn">Submit Application</button>
</form>
<div id="result"></div>
<script>
document.getElementById('app-form').addEventListener('submit', function (e) {
  e.preventDefault();
  document.body.innerHTML = '<h1>Thank you for applying!</h1><p>Your application has been received.</p>';
});
</script>
</body></html>
"""

_FORM_WITHOUT_SUCCESS_HTML = """
<html><body>
<form id="app-form">
  <input type="text" name="full_name">
  <button type="submit" id="submit-btn">Submit Application</button>
</form>
<script>
document.getElementById('app-form').addEventListener('submit', function (e) {
  e.preventDefault();
  document.body.innerHTML = '<h1>Something went wrong, please try again.</h1>';
});
</script>
</body></html>
"""

_FORM_WITHOUT_SUBMIT_BUTTON_HTML = """
<html><body><form><input type="text" name="full_name"></form></body></html>
"""

# The success fixture's "thank you" page contains both phrases; either is a valid match.
_SUCCESS_TEXT_KEYWORDS_IN_FIXTURE = {"thank you for applying", "your application has been received"}


def _job_at_submit_approved(job_id="acme-role"):
    job = {"id": job_id, "metadata": {"company_name": "Acme", "role_title": "Role"}}
    ensure_automation_block(job, source="radar:greenhouse")
    for step in [
        WorkflowStatus.QUALIFIED, WorkflowStatus.ADAPTING, WorkflowStatus.VALIDATING,
        WorkflowStatus.AWAITING_RESUME_APPROVAL, WorkflowStatus.RESUME_APPROVED,
        WorkflowStatus.APPLICATION_PREPARING, WorkflowStatus.AWAITING_APPLICATION_REVIEW,
        WorkflowStatus.READY_TO_SUBMIT, WorkflowStatus.SUBMIT_APPROVED,
    ]:
        transition(job, step)
    return job


def test_find_submit_button_locates_type_submit_button(playwright_page):
    playwright_page.set_content(_FORM_WITH_SUCCESS_HTML)
    button = find_submit_button(playwright_page)
    assert button is not None


def test_find_submit_button_returns_none_when_absent(playwright_page):
    playwright_page.set_content(_FORM_WITHOUT_SUBMIT_BUTTON_HTML)
    assert find_submit_button(playwright_page) is None


def test_detect_submission_success_finds_known_phrase(playwright_page):
    playwright_page.set_content("<html><body><h1>Thank you for applying!</h1></body></html>")
    assert detect_submission_success(playwright_page) == "thank you for applying"


def test_detect_submission_success_returns_none_for_unrecognized_page(playwright_page):
    playwright_page.set_content("<html><body><h1>Some random page</h1></body></html>")
    assert detect_submission_success(playwright_page) is None


def test_submit_application_requires_submit_approved_status(playwright_page):
    job = {"id": "acme-role", "metadata": {}}
    ensure_automation_block(job, source="radar:greenhouse")  # DISCOVERED, not SUBMIT_APPROVED

    with pytest.raises(InvalidTransitionError):
        submit_application(job, page=playwright_page)


def test_submit_application_succeeds_and_transitions_to_applied(playwright_page):
    playwright_page.set_content(_FORM_WITH_SUCCESS_HTML)
    job = _job_at_submit_approved()

    result = submit_application(job, page=playwright_page, wait_after_click_ms=200)

    assert result.submitted is True
    assert result.detected_success_text in _SUCCESS_TEXT_KEYWORDS_IN_FIXTURE
    assert get_workflow_status(job) == WorkflowStatus.APPLIED


def test_submit_application_without_success_indicator_fails_safe(playwright_page):
    playwright_page.set_content(_FORM_WITHOUT_SUCCESS_HTML)
    job = _job_at_submit_approved()

    result = submit_application(job, page=playwright_page, wait_after_click_ms=200)

    assert result.submitted is False
    assert get_workflow_status(job) == WorkflowStatus.FAILED
    assert "não confirmado" in job["automation"]["last_error"]


def test_submit_application_missing_button_fails_without_clicking_anything(playwright_page):
    playwright_page.set_content(_FORM_WITHOUT_SUBMIT_BUTTON_HTML)
    job = _job_at_submit_approved()

    result = submit_application(job, page=playwright_page)

    assert result.submitted is False
    assert get_workflow_status(job) == WorkflowStatus.FAILED
    assert "não encontrado" in job["automation"]["last_error"]
