"""
CLI tool for the Application Prep Agent (Fase 5 / Sprint D).

Runs against every job currently at RESUME_APPROVED: opens the real posting URL in a
real (by default, visible) browser, fills in whatever engine.application.answer_engine
can resolve with confidence, and stops — it never clicks Submit. Jobs move to
AWAITING_APPLICATION_REVIEW; the résumé/materials review lives in Streamlit's Fila de
Aprovação, and marking a job READY_TO_SUBMIT (Gate #2's first half) also happens
there once you've looked at the filled fields and gaps.

Intentionally a CLI script, not a Streamlit button: a real Playwright browser session
against a live third-party site doesn't belong inside a web request/response cycle,
and running it headed (--headless to change that) lets you watch and step in if a
site's form does something unexpected.

Usage:
    python scripts/run_application_agent.py                 # every RESUME_APPROVED job
    python scripts/run_application_agent.py acme-pmm-lead    # just this one job
    python scripts/run_application_agent.py --headless       # no visible browser window
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.application.ats import is_supported
from engine.application.browser import open_browser, open_job_posting_page
from engine.application.session import UnsupportedAtsError, run_application_prep
from engine.automation.state_machine import InvalidTransitionError
from engine.automation.queue_actions import list_resume_approved
from job_store import ROOT as JOB_STORE_ROOT, job_path, load_job, write_json
from utils import load_master_resume


def _resume_pdf_path(job_id: str, lang: str) -> Path | None:
    candidate = (
        JOB_STORE_ROOT / "adaptados para as vagas"
        / f"Curriculo_Kevin_Augusto_Vieira_{job_id}_{lang}.pdf"
    )
    return candidate if candidate.exists() else None


def _run_one(job_id: str, master_resume: dict, *, headless: bool, lang: str) -> None:
    job = load_job(job_id)
    url = job.get("metadata", {}).get("url", "")

    if not is_supported(url):
        print(f"  [SKIP] '{job_id}': ATS não suportado nesta v1 (Greenhouse/Lever/Ashby apenas). URL: {url}")
        return

    print(f"  --> Abrindo '{job_id}' ({url}) ...")
    with open_browser(headless=headless) as browser:
        page = open_job_posting_page(browser, url)
        try:
            session = run_application_prep(
                job,
                master_resume,
                page_factory=lambda: page,
                lang=lang,
                resume_pdf_path=_resume_pdf_path(job_id, lang),
                api_key=os.getenv("OPENROUTER_API_KEY"),
            )
        except InvalidTransitionError as exc:
            print(f"  [ERRO] '{job_id}': {exc}")
            return
        except UnsupportedAtsError as exc:
            print(f"  [SKIP] '{job_id}': {exc}")
            return
        except Exception as exc:  # noqa: BLE001 - já vira BLOCKED dentro de run_application_prep
            print(f"  [BLOCKED] '{job_id}': {exc}")
            write_json(job_path(job_id), job)
            return

        write_json(job_path(job_id), job)
        print(
            f"  [OK] '{job_id}': {len(session.filled)} campo(s) preenchido(s), "
            f"{len(session.human_required)} pendente(s) de revisão humana. "
            "Status: AWAITING_APPLICATION_REVIEW."
        )
        if not headless:
            input("      Pressione Enter para fechar o navegador e seguir para a próxima vaga...")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Application Prep Agent on RESUME_APPROVED jobs.")
    parser.add_argument("job_id", nargs="?", help="Process only this job slug (default: all RESUME_APPROVED jobs)")
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser window")
    parser.add_argument("--lang", default="pt", choices=["pt", "en"], help="Which résumé/materials language to use")
    args = parser.parse_args()

    master_resume = load_master_resume()

    if args.job_id:
        _run_one(args.job_id, master_resume, headless=args.headless, lang=args.lang)
        return

    jobs = list_resume_approved()
    if not jobs:
        print("Nenhuma vaga em RESUME_APPROVED no momento.")
        return

    print(f"{len(jobs)} vaga(s) em RESUME_APPROVED. Iniciando o Application Prep Agent...")
    for job in jobs:
        _run_one(job["id"], master_resume, headless=args.headless, lang=args.lang)


if __name__ == "__main__":
    main()
