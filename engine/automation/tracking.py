"""Generic applications.json writer — the only thing Fase 6 needed to add on the
tracking side. `scripts/register_shortlist_applications.py` (the script that
registered a specific historical batch of manually-submitted applications) is left
untouched: its hardcoded APPLIED_DATE and custom notes text describe something that
already happened, and rewriting it to call this function wouldn't change its
behavior for entries that already exist — only risk it for no real benefit. This
module is the path the *new* automated submit flow (engine/application/submit.py)
uses instead, going forward.

Matches an existing tracker entry for the same job the same way
register_shortlist_applications.py's own `same_application()` always did —
by reusing `engine.automation.dedupe.find_duplicate()` (same normalized
company+role / token-overlap technique, same 0.6 threshold) — so calling this
twice for the same job (e.g. a retried submit) updates the existing row instead of
creating a duplicate.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from job_store import ROOT

APPLICATIONS_PATH = ROOT / "applications.json"


def _read_applications() -> List[Dict[str, Any]]:
    if not APPLICATIONS_PATH.exists():
        return []
    with APPLICATIONS_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _write_applications(applications: List[Dict[str, Any]]) -> None:
    with APPLICATIONS_PATH.open("w", encoding="utf-8") as file:
        json.dump(applications, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _default_stages(applied_date: str) -> List[Dict[str, str]]:
    return [
        {"name": "Candidatura", "status": "Concluído", "date": applied_date},
        {"name": "Triagem (Screening)", "status": "Pendente", "date": ""},
        {"name": "Entrevista de RH", "status": "Pendente", "date": ""},
        {"name": "Entrevista Técnica", "status": "Pendente", "date": ""},
        {"name": "Proposta (Offer)", "status": "Pendente", "date": ""},
    ]


def register_application(
    job: Dict[str, Any],
    submitted_at: str,
    application_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Add (or update) applications.json's entry for a job that was genuinely
    submitted. Intended to be called exactly once, right after
    `engine.application.submit.submit_application()` positively confirms a real
    submission — never earlier, never speculatively.

    `submitted_at` is an ISO timestamp; only its date portion is stored in
    `date_applied`, matching the tracker's existing (date-only) convention.
    `application_meta` lets the caller override/add fields (e.g. custom notes).
    """
    from engine.automation.dedupe import find_duplicate  # deferred: avoid import cycle at module load

    applications = _read_applications()
    metadata = job.get("metadata", {})
    applied_date = submitted_at[:10] if len(submitted_at) >= 10 else submitted_at
    application_meta = dict(application_meta or {})

    existing_id = find_duplicate(
        url=metadata.get("url", ""),
        company=metadata.get("company_name", ""),
        role=metadata.get("role_title", ""),
        existing_jobs=[],
        existing_applications=applications,
    )
    if existing_id:
        # find_duplicate() falls back to f"application:{id}" for tracker rows that have
        # no source_job_id yet (pre-automation manual entries) — unwrap that prefix so
        # it still matches the row's plain "id" field.
        bare_application_id = (
            existing_id.split("application:", 1)[1] if existing_id.startswith("application:") else None
        )
        for entry in applications:
            if (
                entry.get("source_job_id") == existing_id
                or entry.get("id") == existing_id
                or (bare_application_id is not None and entry.get("id") == bare_application_id)
            ):
                entry["source_job_id"] = job["id"]
                entry["status"] = "Candidatado"
                entry["date_applied"] = applied_date
                entry.update(application_meta)
                _write_applications(applications)
                return entry
        # existing_id matched something that isn't actually a row in `applications`
        # (e.g. it pointed at a data/jobs/ artifact id) — fall through and create one.

    next_id = max((int(item["id"]) for item in applications if str(item.get("id", "")).isdigit()), default=0) + 1
    compensation = metadata.get("compensation") or metadata.get("salary_expectation") or "Não informada / a negociar"
    entry = {
        "id": str(next_id),
        "company": metadata.get("company_name", ""),
        "role": metadata.get("role_title", ""),
        "date_applied": applied_date,
        "status": "Candidatado",
        "notes": f"Candidatura enviada automaticamente pelo Application Prep Agent em {applied_date}.",
        "url": metadata.get("url", ""),
        "current_stage": "Candidatura",
        "fit_score": metadata.get("fit_score"),
        "salary_expectation": compensation,
        "good_points": metadata.get("good_points", []),
        "improvement_points": metadata.get("improvement_points", []),
        "source_job_id": job["id"],
        "stages": _default_stages(applied_date),
    }
    entry.update(application_meta)
    applications.append(entry)
    _write_applications(applications)
    return entry
