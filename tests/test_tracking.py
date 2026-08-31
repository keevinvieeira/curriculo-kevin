"""Tests for engine/automation/tracking.py — the generic applications.json writer
used by the automated submit flow (Fase 6)."""
from __future__ import annotations

import json

import pytest

import engine.automation.tracking as tracking_module
from engine.automation.tracking import register_application


@pytest.fixture
def isolated_applications(tmp_path, monkeypatch):
    applications_path = tmp_path / "applications.json"
    applications_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(tracking_module, "APPLICATIONS_PATH", applications_path)
    return applications_path


def _job(
    job_id="acme-role",
    url="https://boards.greenhouse.io/acme/jobs/1",
    company="Acme",
    role="Product Marketing Manager",
):
    return {
        "id": job_id,
        "metadata": {
            "company_name": company,
            "role_title": role,
            "url": url,
            "fit_score": 85,
            "salary_expectation": "R$ 15.000/mês",
            "good_points": ["Ponto forte 1"],
            "improvement_points": ["Ponto de atenção 1"],
        },
    }


def test_register_application_creates_new_entry(isolated_applications):
    entry = register_application(_job(), submitted_at="2026-08-31T12:00:00+00:00")

    assert entry["company"] == "Acme"
    assert entry["role"] == "Product Marketing Manager"
    assert entry["date_applied"] == "2026-08-31"
    assert entry["status"] == "Candidatado"
    assert entry["source_job_id"] == "acme-role"
    assert entry["fit_score"] == 85
    assert len(entry["stages"]) == 5

    on_disk = json.loads(isolated_applications.read_text(encoding="utf-8"))
    assert len(on_disk) == 1
    assert on_disk[0]["id"] == entry["id"]


def test_register_application_assigns_incrementing_ids(isolated_applications):
    entry_1 = register_application(_job("acme-role"), submitted_at="2026-08-31T12:00:00+00:00")
    entry_2 = register_application(
        _job("beta-role", url="https://boards.greenhouse.io/beta/jobs/2", company="Beta", role="Growth Lead"),
        submitted_at="2026-08-31T13:00:00+00:00",
    )
    assert int(entry_2["id"]) == int(entry_1["id"]) + 1
    assert len(json.loads(isolated_applications.read_text())) == 2


def test_register_application_updates_existing_entry_instead_of_duplicating(isolated_applications):
    first = register_application(_job(), submitted_at="2026-08-31T12:00:00+00:00")

    # Same job submitted again (e.g. a retry) — must update, not duplicate.
    second = register_application(_job(), submitted_at="2026-09-01T09:00:00+00:00")

    on_disk = json.loads(isolated_applications.read_text(encoding="utf-8"))
    assert len(on_disk) == 1
    assert second["id"] == first["id"]
    assert second["date_applied"] == "2026-09-01"


def test_register_application_matches_existing_row_by_company_and_role_overlap(isolated_applications):
    # Simulates a pre-existing manually-tracked application for the same real-world
    # job, registered before this job ever went through the automation pipeline.
    applications_path = isolated_applications
    applications_path.write_text(
        json.dumps([
            {
                "id": "1", "company": "Acme", "role": "Product Marketing Manager, Global",
                "url": "https://old-link.example/careers/pmm", "status": "Candidatado",
                "date_applied": "2026-08-01", "stages": [],
            }
        ]),
        encoding="utf-8",
    )

    entry = register_application(_job(), submitted_at="2026-08-31T12:00:00+00:00")

    on_disk = json.loads(applications_path.read_text(encoding="utf-8"))
    assert len(on_disk) == 1  # linked, not duplicated
    assert entry["id"] == "1"
    assert entry["source_job_id"] == "acme-role"


def test_register_application_accepts_custom_meta_overrides(isolated_applications):
    entry = register_application(
        _job(), submitted_at="2026-08-31T12:00:00+00:00",
        application_meta={"notes": "Nota customizada."},
    )
    assert entry["notes"] == "Nota customizada."
