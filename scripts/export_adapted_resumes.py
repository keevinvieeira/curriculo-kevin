"""Render all prioritized resumes and cover letters as PDF files."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.export_job_shortlist import JOB_IDS  # noqa: E402
from utils import (  # noqa: E402
    AdaptedResume,
    JobMaterials,
    convert_html_to_pdf,
    render_html_cover_letter,
    render_html_resume,
)


JOBS_DIR = ROOT / "data" / "jobs"
OUTPUT_DIR = ROOT / "exports" / "curriculos_vagas"
TEMPLATE = ROOT / "templates" / "resume_theme.html"


def read_job(job_id: str) -> dict:
    with (JOBS_DIR / f"{job_id}.json").open(encoding="utf-8") as file:
        return json.load(file)


def export_job(job_id: str) -> int:
    job = read_job(job_id)
    destination = OUTPUT_DIR / job_id
    destination.mkdir(parents=True, exist_ok=True)

    exported = 0
    for language in ("pt", "en"):
        resume = AdaptedResume(**job["resume"][language])
        materials = JobMaterials(**job["materials"][language])

        resume_html = render_html_resume(
            resume,
            target_lang=language,
            template_path=str(TEMPLATE),
        )
        (destination / f"curriculo_{language}.pdf").write_bytes(
            convert_html_to_pdf(resume_html)
        )
        letter_html = render_html_cover_letter(materials.cover_letter)
        (destination / f"carta_{language}.pdf").write_bytes(
            convert_html_to_pdf(letter_html)
        )
        exported += 2
    return exported


def main() -> None:
    total = sum(export_job(job_id) for job_id in JOB_IDS)
    print(f"Exported {total} PDF files for {len(JOB_IDS)} jobs to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
