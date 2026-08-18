"""Register prioritized shortlist jobs in the Streamlit application tracker."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_job_shortlist import JOB_IDS  # noqa: E402


JOBS_DIR = ROOT / "data" / "jobs"
APPLICATIONS_PATH = ROOT / "applications.json"
APPLIED_DATE = "2026-08-18"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def normalize(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold())) - {"at", "de", "do", "em", "or"}


def same_application(application: dict[str, Any], job: dict[str, Any]) -> bool:
    if application.get("source_job_id") == job["id"]:
        return True
    metadata = job["metadata"]
    if normalize(application.get("company", "")) != normalize(metadata["company_name"]):
        return False
    current_role = normalize(application.get("role", ""))
    target_role = normalize(metadata["role_title"])
    if not current_role or not target_role:
        return False
    overlap = len(current_role & target_role) / len(current_role | target_role)
    return overlap >= 0.6


def stages() -> list[dict[str, str]]:
    return [
        {"name": "Candidatura", "status": "Concluído", "date": APPLIED_DATE},
        {"name": "Triagem (Screening)", "status": "Pendente", "date": ""},
        {"name": "Entrevista de RH", "status": "Pendente", "date": ""},
        {"name": "Entrevista Técnica", "status": "Pendente", "date": ""},
        {"name": "Proposta (Offer)", "status": "Pendente", "date": ""},
    ]


def new_application(job: dict[str, Any], application_id: int) -> dict[str, Any]:
    metadata = job["metadata"]
    compensation = (
        metadata.get("compensation")
        or metadata.get("salary_expectation")
        or "Não informada / a negociar"
    )
    return {
        "id": str(application_id),
        "company": metadata["company_name"],
        "role": metadata["role_title"],
        "date_applied": APPLIED_DATE,
        "status": "Candidatado",
        "notes": (
            "Candidatura enviada em 18/08/2026. Materiais PT/EN disponíveis no "
            f"artefato versionado {job['id']}."
        ),
        "url": metadata["url"],
        "current_stage": "Candidatura",
        "fit_score": metadata["fit_score"],
        "salary_expectation": compensation,
        "good_points": metadata.get("good_points", []),
        "improvement_points": metadata.get("improvement_points", []),
        "source_job_id": job["id"],
        "stages": stages(),
    }


def main() -> None:
    applications = read_json(APPLICATIONS_PATH)
    jobs = [read_json(JOBS_DIR / f"{job_id}.json") for job_id in JOB_IDS]
    next_id = max((int(item["id"]) for item in applications if str(item.get("id", "")).isdigit()), default=0) + 1
    added: list[str] = []
    linked: list[str] = []

    for job in jobs:
        existing = next((item for item in applications if same_application(item, job)), None)
        if existing:
            existing.setdefault("source_job_id", job["id"])
            linked.append(job["metadata"]["company_name"])
            continue
        applications.append(new_application(job, next_id))
        next_id += 1
        added.append(job["metadata"]["company_name"])

    with APPLICATIONS_PATH.open("w", encoding="utf-8") as file:
        json.dump(applications, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"Added {len(added)} applications: {', '.join(added)}")
    print(f"Linked {len(linked)} existing applications: {', '.join(linked)}")
    print(f"Tracker total: {len(applications)}")


if __name__ == "__main__":
    main()
