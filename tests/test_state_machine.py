"""Tests for engine/automation/state_machine.py."""
from __future__ import annotations

import pytest

from engine.automation.state_machine import (
    InvalidTransitionError,
    WorkflowStatus,
    ensure_automation_block,
    get_workflow_status,
    transition,
)


def _new_job() -> dict:
    return {
        "id": "acme-product-marketer",
        "metadata": {"company_name": "Acme", "role_title": "Product Marketer"},
    }


def test_legacy_job_without_automation_block_has_no_status():
    job = _new_job()
    assert get_workflow_status(job) is None


def test_ensure_automation_block_defaults_to_discovered():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    assert get_workflow_status(job) == WorkflowStatus.DISCOVERED
    assert job["automation"]["source"] == "radar"
    assert job["automation"]["discovered_at"] is not None


def test_ensure_automation_block_is_idempotent():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    transition(job, WorkflowStatus.QUALIFIED)
    ensure_automation_block(job, source="radar")  # chamado de novo, não deve resetar
    assert get_workflow_status(job) == WorkflowStatus.QUALIFIED


def test_transition_without_automation_block_raises():
    job = _new_job()
    with pytest.raises(InvalidTransitionError, match="ensure_automation_block"):
        transition(job, WorkflowStatus.QUALIFIED)


def test_full_happy_path_reaches_ready_to_submit():
    job = _new_job()
    ensure_automation_block(job, source="radar")

    path = [
        WorkflowStatus.QUALIFIED,
        WorkflowStatus.ADAPTING,
        WorkflowStatus.VALIDATING,
        WorkflowStatus.AWAITING_RESUME_APPROVAL,
        WorkflowStatus.RESUME_APPROVED,
        WorkflowStatus.APPLICATION_PREPARING,
        WorkflowStatus.AWAITING_APPLICATION_REVIEW,
        WorkflowStatus.READY_TO_SUBMIT,
        WorkflowStatus.SUBMIT_APPROVED,
        WorkflowStatus.APPLIED,
    ]
    for status in path:
        transition(job, status)

    assert get_workflow_status(job) == WorkflowStatus.APPLIED
    automation = job["automation"]
    assert automation["resume_approved_at"] is not None
    assert automation["application_started_at"] is not None
    assert automation["application_ready_at"] is not None
    assert automation["submit_approved_at"] is not None
    assert automation["submitted_at"] is not None


def test_cannot_skip_gate_1_straight_to_resume_approved():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    transition(job, WorkflowStatus.QUALIFIED)
    transition(job, WorkflowStatus.ADAPTING)
    transition(job, WorkflowStatus.VALIDATING)
    # ainda em VALIDATING — pular direto para RESUME_APPROVED sem passar por
    # AWAITING_RESUME_APPROVAL (ou seja, sem o gate humano #1) deve falhar.
    with pytest.raises(InvalidTransitionError):
        transition(job, WorkflowStatus.RESUME_APPROVED)


def test_cannot_skip_gate_2_straight_to_applied():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    for status in [
        WorkflowStatus.QUALIFIED,
        WorkflowStatus.ADAPTING,
        WorkflowStatus.VALIDATING,
        WorkflowStatus.AWAITING_RESUME_APPROVAL,
        WorkflowStatus.RESUME_APPROVED,
        WorkflowStatus.APPLICATION_PREPARING,
        WorkflowStatus.AWAITING_APPLICATION_REVIEW,
        WorkflowStatus.READY_TO_SUBMIT,
    ]:
        transition(job, status)
    # READY_TO_SUBMIT -> APPLIED direto, pulando SUBMIT_APPROVED (gate humano #2), deve falhar.
    with pytest.raises(InvalidTransitionError):
        transition(job, WorkflowStatus.APPLIED)


def test_terminal_states_accept_no_further_transitions():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    transition(job, WorkflowStatus.DISCARDED)
    with pytest.raises(InvalidTransitionError):
        transition(job, WorkflowStatus.QUALIFIED)


def test_failed_records_error_and_can_be_retried():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    transition(job, WorkflowStatus.QUALIFIED)
    transition(job, WorkflowStatus.ADAPTING)
    transition(job, WorkflowStatus.FAILED, error="Gemini timeout")
    assert job["automation"]["last_error"] == "Gemini timeout"

    transition(job, WorkflowStatus.ADAPTING)  # retry
    assert job["automation"]["last_error"] is None
    assert get_workflow_status(job) == WorkflowStatus.ADAPTING


def test_hold_preserves_last_error_and_can_resume():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    transition(job, WorkflowStatus.QUALIFIED)
    transition(job, WorkflowStatus.HOLD)
    transition(job, WorkflowStatus.QUALIFIED)  # retoma
    assert get_workflow_status(job) == WorkflowStatus.QUALIFIED


def test_unknown_status_string_raises():
    job = _new_job()
    ensure_automation_block(job, source="radar")
    with pytest.raises(InvalidTransitionError, match="Status desconhecido"):
        transition(job, "NOT_A_REAL_STATUS")
