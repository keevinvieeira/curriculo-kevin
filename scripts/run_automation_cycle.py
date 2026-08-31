"""
CLI tool for the radar + adaptation half of the automation layer (Fase 7).

Runs entirely without human intervention, and stops at the first human gate: it
discovers postings from the boards configured in `automation_sources.json`,
deduplicates against `data/jobs/*.json` and `applications.json`, scores each one
deterministically, and adapts (via OpenRouter) whatever passes the fit gate — up to
`--max-jobs` per run, to bound LLM API cost. New/updated job artifacts land in
`data/jobs/<slug>.json` at AWAITING_RESUME_APPROVAL; nothing here ever activates a
job in Streamlit or writes to applications.json.

This is the half of the pipeline meant to run unattended, on a schedule, in the
cloud (see `.github/workflows/automation_cycle.yml`) — the Application Prep Agent
(Fase 5, `scripts/run_application_agent.py`) and the submit agent (Fase 6,
`scripts/run_submit_agent.py`) are the other half, and both need a real local
browser session (and, for a site requiring login, the user's own cookies), so they
stay local-only. See README.md's "Automação" section for the full cloud/local split.

Usage:
    python scripts/run_automation_cycle.py                       # default cap (5)
    python scripts/run_automation_cycle.py --max-jobs 10
    python scripts/run_automation_cycle.py --min-salary 12000     # BRL/month floor
    python scripts/run_automation_cycle.py --no-pdf               # skip PDF export (faster CI runs)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.automation.radar import AshbySource, GreenhouseSource, LeverSource
from engine.automation.workflow import DEFAULT_MAX_JOBS_PER_CYCLE, run_automation_cycle
from job_store import list_jobs
from utils import load_master_resume

SOURCES_CONFIG_PATH = ROOT / "automation_sources.json"
APPLICATIONS_PATH = ROOT / "applications.json"


def _load_sources_config() -> dict:
    if not SOURCES_CONFIG_PATH.exists():
        return {"greenhouse_boards": [], "lever_accounts": [], "ashby_boards": []}
    with SOURCES_CONFIG_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _build_sources(config: dict) -> list:
    sources = []
    if config.get("greenhouse_boards"):
        sources.append(GreenhouseSource(config["greenhouse_boards"]))
    if config.get("lever_accounts"):
        sources.append(LeverSource(config["lever_accounts"]))
    if config.get("ashby_boards"):
        sources.append(AshbySource(config["ashby_boards"]))
    return sources


def _load_existing_applications() -> list:
    if not APPLICATIONS_PATH.exists():
        return []
    with APPLICATIONS_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one radar -> dedupe -> score -> adapt cycle.")
    parser.add_argument(
        "--max-jobs", type=int, default=DEFAULT_MAX_JOBS_PER_CYCLE,
        help=f"Cap on jobs adapted this cycle (default: {DEFAULT_MAX_JOBS_PER_CYCLE})",
    )
    parser.add_argument("--min-salary", type=float, default=None, help="Minimum acceptable monthly salary (BRL)")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (faster, e.g. in CI)")
    args = parser.parse_args()

    config = _load_sources_config()
    sources = _build_sources(config)
    if not sources:
        print(
            f"Nenhuma fonte configurada em {SOURCES_CONFIG_PATH.name}. "
            "Preencha greenhouse_boards/lever_accounts/ashby_boards com os slugs das "
            "empresas que você quer monitorar antes de rodar o radar."
        )
        return

    master_resume = load_master_resume()
    existing_jobs = list_jobs()
    existing_applications = _load_existing_applications()

    print(f"Rodando o radar em {len(sources)} fonte(s) configurada(s)...")
    report = run_automation_cycle(
        sources,
        master_resume,
        existing_jobs=existing_jobs,
        existing_applications=existing_applications,
        max_jobs_per_cycle=args.max_jobs,
        min_salary_expected=args.min_salary,
        generate_pdfs=not args.no_pdf,
    )

    print(f"Descobertas: {report.discovered}")
    print(f"Duplicatas ignoradas: {report.duplicates_skipped}")
    print(f"Abaixo do fit_score gate: {report.below_gate_skipped}")
    print(f"Adiadas (acima do teto do ciclo): {report.deferred}")
    print(f"Adaptadas com sucesso ({len(report.adapted)}): {', '.join(report.adapted) or '(nenhuma)'}")
    if report.failed:
        print(f"Falharam na adaptação/validação ({len(report.failed)}):")
        for failure in report.failed:
            print(f"  - {failure['posting']}: {failure['error']}")
    if report.source_errors:
        print(f"Fontes com erro ({len(report.source_errors)}):")
        for source_error in report.source_errors:
            print(f"  - {source_error['source']}: {source_error['error']}")

    if report.adapted:
        print(
            "\nVagas prontas em data/jobs/*.json com workflow_status=AWAITING_RESUME_APPROVAL. "
            "Revise-as na aba 'Fila de Aprovação (Radar)' do Streamlit."
        )


if __name__ == "__main__":
    main()
