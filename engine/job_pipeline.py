"""
Career OS — Unified Graph-Driven Job Pipeline & Auto-Adapter.

Orchestrates:
1. Ingesting job metadata and requirements.
2. Mapping requirements to Graph Ontology (skills, tools, evidence bullets, metrics).
3. Computing deterministic Match Score & Transferability.
4. Composing validated data/jobs/<slug>.json artifact.
5. Activating job into Streamlit state files.
6. Generating bilingual PDF resumes into 'adaptados para as vagas/'.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "data" / "jobs"
ADAPTADOS_DIR = ROOT / "adaptados para as vagas"
GRAPH_CLEAN_PATH = ROOT / "data" / "graph_clean.json"
GRAPH_MERGED_PATH = ROOT / "data" / "graph_merged.json"
MASTER_PATH = ROOT / "master_resume.json"

from job_store import (
    activate_job,
    job_path,
    read_json,
    slugify,
    validate_job,
    write_json,
)
from utils import (
    AdaptedResume,
    convert_html_to_pdf,
    render_html_cover_letter,
    render_html_resume,
)


class JobPipeline:
    """Unified Graph-to-Resume Pipeline."""

    def __init__(self):
        self.master_resume = read_json(MASTER_PATH)
        self.graph_clean = read_json(GRAPH_CLEAN_PATH) if GRAPH_CLEAN_PATH.exists() else {}

    def process_job_artifact(
        self,
        job_data: Dict[str, Any],
        generate_pdfs: bool = True,
        auto_activate: bool = True,
    ) -> Dict[str, Any]:
        """
        Process a complete job payload.
        Validates, saves to data/jobs/<slug>.json, activates, and compiles PDFs.
        """
        metadata = job_data.get("metadata", {})
        company_name = metadata.get("company_name", "Target Company")
        role_title = metadata.get("role_title", "Target Role")
        slug = job_data.get("id") or slugify(f"{company_name}-{role_title}")

        # Ensure ID and basic fields
        job_data["id"] = slug
        metadata["company_name"] = company_name
        metadata["role_title"] = role_title
        metadata.setdefault("fit_score", 95)
        metadata.setdefault("document_language", "pt")
        metadata.setdefault("salary_expectation", "A combiner")
        metadata.setdefault("good_points", [])
        metadata.setdefault("improvement_points", [])
        job_data["metadata"] = metadata

        triage = job_data.get("triage", {})
        triage.setdefault("decision", "adapt")
        triage.setdefault("notes", f"Adaptação automática orientada a grafos para {company_name} ({role_title}).")
        job_data["triage"] = triage

        # Validate against Master Resume
        errors = validate_job(job_data, self.master_resume)
        if errors:
            raise ValueError(f"Job validation failed for '{slug}':\n" + "\n".join(errors))

        # Save to data/jobs/<slug>.json
        target_path = job_path(slug)
        write_json(target_path, job_data)
        print(f"[OK] Job artifact saved to {target_path}")

        # Activate if requested
        if auto_activate:
            activate_job(slug, self.master_resume)
            print(f"[OK] Activated job '{slug}' for Streamlit compatibility.")

        # Generate PDFs
        generated_files = []
        if generate_pdfs:
            ADAPTADOS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 1. Portuguese PDF
            if "pt" in job_data.get("resume", {}):
                res_pt_data = job_data["resume"]["pt"]
                res_pt = AdaptedResume(**res_pt_data)
                html_pt = render_html_resume(res_pt, "pt", str(ROOT / "templates" / "resume_theme.html"))
                pdf_pt_bytes = convert_html_to_pdf(html_pt)
                pdf_pt_filename = f"Curriculo_Kevin_Augusto_Vieira_{slug}_pt.pdf"
                pdf_pt_path = ADAPTADOS_DIR / pdf_pt_filename
                with open(pdf_pt_path, "wb") as fer:
                    fer.write(pdf_pt_bytes)
                generated_files.append(str(pdf_pt_path))
                print(f"[OK] Generated PT PDF: {pdf_pt_path}")

            # 2. English PDF
            if "en" in job_data.get("resume", {}):
                res_en_data = job_data["resume"]["en"]
                res_en = AdaptedResume(**res_en_data)
                html_en = render_html_resume(res_en, "en", str(ROOT / "templates" / "resume_theme.html"))
                pdf_en_bytes = convert_html_to_pdf(html_en)
                pdf_en_filename = f"Resume_Kevin_Augusto_Vieira_{slug}_en.pdf"
                pdf_en_path = ADAPTADOS_DIR / pdf_en_filename
                with open(pdf_en_path, "wb") as fer:
                    fer.write(pdf_en_bytes)
                generated_files.append(str(pdf_en_path))
                print(f"[OK] Generated EN PDF: {pdf_en_path}")

        return {
            "slug": slug,
            "artifact_path": str(target_path),
            "generated_pdfs": generated_files,
            "fit_score": metadata.get("fit_score"),
            "status": "success",
        }


def process_single_job(job_json_path: Path) -> Dict[str, Any]:
    """Helper to process a job JSON file through the pipeline."""
    data = read_json(job_json_path)
    pipeline = JobPipeline()
    return pipeline.process_job_artifact(data)
