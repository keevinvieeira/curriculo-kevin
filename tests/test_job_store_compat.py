"""Confirms the new `automation` block is fully backward-compatible with job_store.

validate_job() must keep accepting jobs with no `automation` key at all (every job
created before this sprint), and also accept jobs that do have one (added by the
automation layer) — the block is pure addition, never a new requirement.
"""
from __future__ import annotations

import copy

import pytest

from engine.automation.state_machine import (
    WorkflowStatus,
    ensure_automation_block,
    transition,
)
from job_store import JOBS_DIR, ROOT, read_json, validate_job

_SAMPLE_JOB_PATH = JOBS_DIR / "doctoralia-noa-gtm-revenue-operations-specialist.json"


@pytest.fixture
def master_resume():
    return read_json(ROOT / "master_resume.json")


@pytest.fixture
def sample_job():
    if not _SAMPLE_JOB_PATH.exists():
        pytest.skip(f"Sample job fixture not found at {_SAMPLE_JOB_PATH}")
    return read_json(_SAMPLE_JOB_PATH)


def test_legacy_job_without_automation_block_still_validates(sample_job, master_resume):
    assert "automation" not in sample_job
    assert validate_job(sample_job, master_resume) == []


def test_job_with_automation_block_still_validates(sample_job, master_resume):
    job = copy.deepcopy(sample_job)
    ensure_automation_block(job, source="radar")
    transition(job, WorkflowStatus.QUALIFIED)
    assert validate_job(job, master_resume) == []
