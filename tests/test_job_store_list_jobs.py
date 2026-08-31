"""Tests for job_store.list_jobs() — the enumeration the Streamlit approval queue
(Fase 4) relies on to find every data/jobs/<slug>.json artifact."""
from __future__ import annotations

import json

import pytest

import job_store


@pytest.fixture
def isolated_jobs_dir(tmp_path, monkeypatch):
    jobs_dir = tmp_path / "data" / "jobs"
    jobs_dir.mkdir(parents=True)
    monkeypatch.setattr(job_store, "JOBS_DIR", jobs_dir)
    monkeypatch.setattr(job_store, "ACTIVE_POINTER", jobs_dir / "active.json")
    return jobs_dir


def _write(jobs_dir, name, content):
    (jobs_dir / name).write_text(json.dumps(content), encoding="utf-8")


def test_list_jobs_returns_empty_list_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "JOBS_DIR", tmp_path / "does-not-exist")
    assert job_store.list_jobs() == []


def test_list_jobs_skips_active_pointer_file(isolated_jobs_dir):
    _write(isolated_jobs_dir, "active.json", {"job_id": "acme-role"})
    _write(isolated_jobs_dir, "acme-role.json", {"id": "acme-role", "metadata": {}})

    jobs = job_store.list_jobs()

    assert [job["id"] for job in jobs] == ["acme-role"]


def test_list_jobs_skips_unparseable_files_without_crashing(isolated_jobs_dir):
    (isolated_jobs_dir / "corrupted.json").write_text("{not valid json", encoding="utf-8")
    _write(isolated_jobs_dir, "acme-role.json", {"id": "acme-role", "metadata": {}})

    jobs = job_store.list_jobs()

    assert [job["id"] for job in jobs] == ["acme-role"]


def test_list_jobs_returns_all_valid_job_artifacts(isolated_jobs_dir):
    _write(isolated_jobs_dir, "acme-role.json", {"id": "acme-role", "metadata": {}})
    _write(isolated_jobs_dir, "gamma-role.json", {"id": "gamma-role", "metadata": {}})

    jobs = job_store.list_jobs()

    assert sorted(job["id"] for job in jobs) == ["acme-role", "gamma-role"]
