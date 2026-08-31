"""
CLI tool that actually submits applications (Fase 6 / Sprint E) — the one script in
this whole project that clicks a real Submit button.

Only touches jobs already SUBMIT_APPROVED: a human already reviewed the filled form
(Streamlit's Fila de Aprovação, "Revisão do preenchimento") and explicitly approved
sending it (the "🚀 Gate #2 — Aprovar Envio" button, also in Streamlit) before this
script ever runs. Nothing here can promote a job to SUBMIT_APPROVED itself.

Re-fills the form from scratch immediately before submitting (rather than trying to
keep one browser session open across the entire review period, which could be hours
or days) — job["resume"]/job["materials"] are deterministic, so this reproduces the
exact same filled state Fase 5 already produced and reviewed, then submits in the
same continuous run.

Requires --yes to actually click Submit; without it, this only re-fills the form,
shows what it found, and stops (a safe rehearsal/dry-run of everything up to the
irreversible step).

Usage:
    python scripts/run_submit_agent.py                  # dry-run every SUBMIT_APPROVED job
    python scripts/run_submit_agent.py acme-pmm-lead     # just this one job
    python scripts/run_submit_agent.py --yes             # actually submit, for real
    python scripts/run_submit_agent.py --headless --yes  # same, no visible browser window
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.application.ats import is_supported
from engine.application.browser import open_browser, open_job_posting_page
from engine.application.session import fill_application_form
from engine.application.submit import submit_application
from engine.automation.queue_actions import list_ready_to_submit  # noqa: F401 (kept for parity/future use)
from engine.automation.state_machine import InvalidTransitionError, WorkflowStatus, get_workflow_status
from engine.automation.tracking import register_application
from job_store import ROOT as JOB_STORE_ROOT, job_path, list_jobs, load_job, write_json
from utils import load_master_resume


def _resume_pdf_path(job_id: str, lang: str) -> Path | None:
    candidate = (
        JOB_STORE_ROOT / "adaptados para as vagas"
        / f"Curriculo_Kevin_Augusto_Vieira_{job_id}_{lang}.pdf"
    )
    return candidate if candidate.exists() else None


def _submit_approved_jobs():
    return [job for job in list_jobs() if get_workflow_status(job) == WorkflowStatus.SUBMIT_APPROVED]


def _run_one(job_id: str, master_resume: dict, *, headless: bool, lang: str, confirm: bool) -> None:
    job = load_job(job_id)
    current_status = get_workflow_status(job)
    if current_status != WorkflowStatus.SUBMIT_APPROVED:
        print(
            f"  [SKIP] '{job_id}': não está SUBMIT_APPROVED (status atual: "
            f"{current_status.value if current_status else 'sem automation'}). "
            "Aprove o envio na Fila de Aprovação do Streamlit primeiro."
        )
        return

    url = job.get("metadata", {}).get("url", "")
    if not is_supported(url):
        print(f"  [SKIP] '{job_id}': ATS não suportado. URL: {url}")
        return

    print(f"  --> Reabrindo e repreenchendo '{job_id}' ({url}) ...")
    with open_browser(headless=headless) as browser:
        page = open_job_posting_page(browser, url)
        session = fill_application_form(
            page, job, master_resume, lang=lang,
            resume_pdf_path=_resume_pdf_path(job_id, lang),
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        print(
            f"      Repreenchido: {len(session.filled)} campo(s) ok, "
            f"{len(session.human_required)} pendente(s)."
        )

        if not confirm:
            print("      [DRY-RUN] Rode de novo com --yes para realmente clicar em Enviar.")
            if not headless:
                input("      Pressione Enter para fechar o navegador...")
            return

        try:
            result = submit_application(job, page=page)
        except InvalidTransitionError as exc:
            print(f"  [ERRO] '{job_id}': {exc}")
            return

        write_json(job_path(job_id), job)

        if not result.submitted:
            print(f"  [FALHOU] '{job_id}': {result.error}. Job marcado como FAILED, revise manualmente.")
            return

        submitted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        register_application(job, submitted_at, application_meta={
            "notes": f"Candidatura enviada pelo Application Prep Agent ({result.detected_success_text!r}).",
        })
        print(f"  [ENVIADO] '{job_id}': confirmado via {result.detected_success_text!r}. Status: APPLIED.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit SUBMIT_APPROVED job applications for real.")
    parser.add_argument("job_id", nargs="?", help="Process only this job slug (default: all SUBMIT_APPROVED jobs)")
    parser.add_argument("--yes", action="store_true", help="Actually click Submit (default: dry-run only)")
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser window")
    parser.add_argument("--lang", default="pt", choices=["pt", "en"], help="Which résumé/materials language to use")
    args = parser.parse_args()

    master_resume = load_master_resume()

    if args.job_id:
        _run_one(args.job_id, master_resume, headless=args.headless, lang=args.lang, confirm=args.yes)
        return

    jobs = _submit_approved_jobs()
    if not jobs:
        print("Nenhuma vaga em SUBMIT_APPROVED no momento.")
        return

    print(f"{len(jobs)} vaga(s) em SUBMIT_APPROVED.{' Enviando de verdade.' if args.yes else ' Modo dry-run.'}")
    for job in jobs:
        _run_one(job["id"], master_resume, headless=args.headless, lang=args.lang, confirm=args.yes)


if __name__ == "__main__":
    main()
