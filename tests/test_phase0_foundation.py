"""Fase 0: stable master IDs, v2 evidence map, dated application status history."""
from __future__ import annotations

import copy

import pytest

from application_history import derive_history, set_status, sync_history
from job_store import ROOT, read_json, validate_evidence_map
from resume_ids import assign_ids, build_index, validate_ids


@pytest.fixture
def master():
    return read_json(ROOT / "master_resume.json")


@pytest.fixture
def evidence():
    return read_json(ROOT / "data" / "schemas" / "examples" / "wellhub-evidence-map.json")


# --- master IDs ---------------------------------------------------------------

def test_master_ids_are_complete_and_consistent(master):
    assert validate_ids(master) == []


def test_assign_ids_is_idempotent(master):
    before = copy.deepcopy(master)
    assert assign_ids(master) == []
    assert master == before


def test_new_bullet_gets_next_number_without_renumbering(master):
    wipro = next(e for e in master["work_experience"] if e["id"] == "exp-wipro")
    existing = [b["id"] for b in wipro["bullets"]]
    wipro["bullets"].insert(0, {"tags": [], "pt": "novo", "en": "new"})
    assert assign_ids(master) == ["wipro-b16"]
    assert [b["id"] for b in wipro["bullets"][1:]] == existing


def test_mirrored_company_bullets_share_the_project_bullet_id(master):
    index = build_index(master)
    ai_builder = next(e for e in master["work_experience"] if e["id"] == "exp-ai-builder")
    for bullet in ai_builder["bullets"]:
        assert index[bullet["id"]]["project_id"] is not None


def test_edited_mirror_is_flagged(master):
    ai_builder = next(e for e in master["work_experience"] if e["id"] == "exp-ai-builder")
    ai_builder["bullets"][0]["pt"] += " (editado só aqui)"
    assert any("duplicate id with different content" in e for e in validate_ids(master))


# --- evidence map -------------------------------------------------------------

def test_example_evidence_map_is_valid(evidence, master):
    assert validate_evidence_map(evidence, master) == []


def test_empty_or_legacy_evidence_is_accepted(master):
    assert validate_evidence_map({"skills": {"pt": [], "en": []}}, master) == []
    assert validate_evidence_map({"skills": {}, "requirements": [], "gaps": []}, master) == []


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (lambda ev: ev["requirements"][1]["evidence_ids"].append("wipro-b99"), "not found in master"),
        (lambda ev: ev["requirements"][1].update(evidence_ids=[]), "requires at least one evidence_id"),
        (lambda ev: ev["requirements"][5].update(evidence_ids=["wipro-b01"]), "gap must not cite"),
        (lambda ev: ev["gaps"].pop(), "needs an entry in evidence.gaps"),
        (lambda ev: ev["requirements"][0].update(status="fluent"), "status must be"),
        (lambda ev: ev["gaps"][0].update(severity="huge"), "severity must be"),
        (lambda ev: ev["requirements"][1].update(id="req-01"), "duplicated"),
    ],
)
def test_evidence_map_rejects_broken_entries(evidence, master, mutate, expected):
    mutate(evidence)
    assert any(expected in e for e in validate_evidence_map(evidence, master))


# --- application status history ----------------------------------------------

def test_history_uses_only_recorded_dates():
    app = {
        "status": "Rejeitado",
        "date_applied": "2026-09-15",
        "date_rejected": "2026-09-23",
        "stages": [
            {"name": "Entrevista RH", "status": "Concluído", "date": ""},
            {"name": "Entrevista com Gestor", "status": "Concluído", "date": "2026-09-18"},
            {"name": "RH / Proposta", "status": "Encerrado", "date": "2026-09-23"},
        ],
    }
    history = derive_history(app)
    assert [(h["status"], h["date"]) for h in history] == [
        ("Candidatado", "2026-09-15"),
        ("Entrevista", "2026-09-18"),
        ("Rejeitado", "2026-09-23"),
    ]
    assert "etapa anterior sem data" in history[1]["note"]


def test_history_never_invents_a_date():
    app = {"status": "Triagem", "date_applied": "2026-09-01", "stages": []}
    assert derive_history(app)[-1] == {
        "status": "Triagem", "date": None, "source": "migration",
        "note": "data não registrada no histórico original",
    }


def test_set_status_appends_and_sync_catches_direct_writes():
    app = {"status": "Candidatado", "date_applied": "2026-09-01"}
    set_status(app, "Triagem", date="2026-09-05", source="app")
    set_status(app, "Triagem", date="2026-09-06", source="app")  # no-op
    app["status"] = "Entrevista"  # a writer that bypassed set_status
    sync_history(app)
    assert [h["status"] for h in app["status_history"]] == ["Candidatado", "Triagem", "Entrevista"]
    assert app["status_history"][1]["date"] == "2026-09-05"


def test_every_application_has_history_ending_in_current_status():
    for app in read_json(ROOT / "applications.json"):
        assert app["status_history"][-1]["status"] == app["status"], app["id"]
        assert app["status_history"][0]["status"] == "Candidatado", app["id"]
