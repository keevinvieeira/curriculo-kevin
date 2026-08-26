"""Single-file job artifacts with legacy Streamlit export compatibility."""

from __future__ import annotations

import json
import re
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
JOBS_DIR = ROOT / "data" / "jobs"
ACTIVE_POINTER = JOBS_DIR / "active.json"
LANGUAGES = ("pt", "en")
FORBIDDEN_TITLES = ("founder", "co-founder", "fundador", "cofundador")


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "job"


def job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{slugify(job_id)}.json"


def load_job(job_id: str) -> dict[str, Any]:
    return read_json(job_path(job_id))


def load_active_job() -> dict[str, Any] | None:
    if not ACTIVE_POINTER.exists():
        return None
    pointer = read_json(ACTIVE_POINTER)
    return load_job(pointer["job_id"])


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return str(value)


def _master_skills(master_resume: dict[str, Any]) -> set[str]:
    skills = set()
    for language_skills in master_resume.get("technical_skills", {}).values():
        for category in language_skills:
            skills.update(skill.casefold() for skill in category.get("skills", []))
    return skills


def validate_job(job: dict[str, Any], master_resume: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metadata = job.get("metadata", {})
    if not metadata.get("company_name") or not metadata.get("role_title"):
        errors.append("metadata must include company_name and role_title")

    for section in ("resume", "materials"):
        for language in LANGUAGES:
            if not job.get(section, {}).get(language):
                errors.append(f"{section}.{language} is required")

    triage = job.get("triage", {})
    if triage.get("decision") not in {"adapt", "hold", "discard"}:
        errors.append("triage.decision must be adapt, hold, or discard")

    # Títulos reais do master resume (fatos legítimos, mesmo que contenham founder/co-founder)
    master_titles = set()
    for item in master_resume.get("work_experience", []):
        for role in item.get("roles", []):
            title = role.get("title") if isinstance(role, dict) else None
            if isinstance(title, dict):
                for v in title.values():
                    if isinstance(v, str):
                        master_titles.add(v.casefold())
            elif isinstance(title, str):
                master_titles.add(title.casefold())

    for language, resume in job.get("resume", {}).items():
        if not resume.get("summary"):
            errors.append(f"resume.{language}.summary is required")
        for experience in resume.get("experience", []):
            title = experience.get("role", "").casefold()
            if any(forbidden in title for forbidden in FORBIDDEN_TITLES):
                # Permite se o título existe de fato no master resume (cargo real)
                if title not in master_titles:
                    errors.append(f"resume.{language} contains forbidden role title: {experience.get('role')}")

    company = metadata.get("company_name", "").casefold()
    for language, materials in job.get("materials", {}).items():
        cover_letter = materials.get("cover_letter", "").casefold()
        if company and company not in cover_letter:
            errors.append(f"materials.{language}.cover_letter does not mention the target company")

    master_skills = _master_skills(master_resume)
    for language, declared in job.get("evidence", {}).get("skills", {}).items():
        for skill in declared:
            if skill.casefold() not in master_skills:
                errors.append(f"evidence.skills.{language} contains skill absent from master resume: {skill}")

    return errors


def activate_job(job_id: str, master_resume: dict[str, Any] | None = None) -> dict[str, Any]:
    job = load_job(job_id)
    if master_resume is not None:
        errors = validate_job(job, master_resume)
        if errors:
            raise ValueError("\n".join(errors))

    write_json(ACTIVE_POINTER, {"job_id": job["id"]})
    write_json(ROOT / "metadata.json", job["metadata"])
    for language in LANGUAGES:
        write_json(ROOT / f"adapted_resume_{language}.json", job["resume"][language])
        write_json(ROOT / f"job_materials_{language}.json", job["materials"][language])

    # Keep the historical generic files usable for older app links.
    default_language = job["metadata"].get("document_language", "pt")
    shutil.copyfile(ROOT / f"adapted_resume_{default_language}.json", ROOT / "adapted_resume.json")
    shutil.copyfile(ROOT / f"job_materials_{default_language}.json", ROOT / "job_materials.json")
    return job


def create_from_active(job_id: str, triage: dict[str, Any] | None = None) -> dict[str, Any]:
    job = {
        "id": slugify(job_id),
        "metadata": read_json(ROOT / "metadata.json"),
        "triage": triage or {"decision": "adapt", "blockers": [], "notes": []},
        "resume": {language: read_json(ROOT / f"adapted_resume_{language}.json") for language in LANGUAGES},
        "materials": {language: read_json(ROOT / f"job_materials_{language}.json") for language in LANGUAGES},
        "evidence": {"skills": {"pt": [], "en": []}},
    }
    write_json(job_path(job["id"]), job)
    return job


def clone_job(source_job_id: str, target_job_id: str) -> dict[str, Any]:
    job = deepcopy(load_job(source_job_id))
    job["id"] = slugify(target_job_id)
    write_json(job_path(job["id"]), job)
    return job
