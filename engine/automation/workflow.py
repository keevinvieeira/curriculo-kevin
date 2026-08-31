"""Orchestrates one full automation cycle: radar -> dedupe -> score -> ingest.

This is what `scripts/run_automation_cycle.py` calls. Everything here stops at
AWAITING_RESUME_APPROVAL — nothing in this module ever touches the Application Prep
Agent or the submit gate, and nothing here can run unattended past the first human
gate.

The per-cycle cap (`max_jobs_per_cycle`) exists specifically to bound LLM API cost and
the size of the human approval queue: a radar that suddenly turns up 40 matching
postings in one run should adapt the best few now and leave the rest for next cycle,
not fire 160 LLM calls (résumé pt/en + materials pt/en per job) at once.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from engine.automation.dedupe import find_duplicate
from engine.automation.ingestion import IngestionError, adapt_and_ingest
from engine.automation.radar import JobSource, RawJobPosting, discover_all
from engine.automation.scoring import ScoreResult, score_job
from engine.job_pipeline import JobPipeline

DEFAULT_MAX_JOBS_PER_CYCLE = 5


@dataclass
class CycleReport:
    discovered: int = 0
    duplicates_skipped: int = 0
    below_gate_skipped: int = 0
    adapted: List[str] = field(default_factory=list)  # slugs successfully ingested
    failed: List[Dict[str, str]] = field(default_factory=list)  # [{"posting": ..., "error": ...}]
    source_errors: List[Dict[str, str]] = field(default_factory=list)
    deferred: int = 0  # passou no gate mas ficou de fora por causa do teto do ciclo


def run_automation_cycle(
    sources: List[JobSource],
    master_resume: Dict[str, Any],
    *,
    existing_jobs: List[Dict[str, Any]],
    existing_applications: List[Dict[str, Any]],
    max_jobs_per_cycle: int = DEFAULT_MAX_JOBS_PER_CYCLE,
    min_salary_expected: Optional[float] = None,
    pipeline: Optional[JobPipeline] = None,
    generate_pdfs: bool = True,
) -> CycleReport:
    """Run discovery -> dedupe -> scoring -> (capped) adaptation for one cycle.

    `existing_jobs`/`existing_applications` are passed in rather than read from disk
    here, so this function stays easy to unit test and so callers control exactly
    which snapshot of data/jobs/ + applications.json to dedupe against.
    """
    report = CycleReport()

    postings, source_errors = discover_all(sources)
    report.discovered = len(postings)
    report.source_errors = [{"source": e.source_name, "error": e.error} for e in source_errors]

    scored: List[tuple[RawJobPosting, ScoreResult]] = []
    for posting in postings:
        if find_duplicate(
            url=posting.url,
            company=posting.company,
            role=posting.title,
            existing_jobs=existing_jobs,
            existing_applications=existing_applications,
        ):
            report.duplicates_skipped += 1
            continue

        result = score_job(
            title=posting.title,
            description=posting.description,
            location=posting.location,
            remote=posting.remote,
            salary_range=posting.salary_range,
            posted_at=posting.posted_at,
            min_salary_expected=min_salary_expected,
        )
        if not result.passes_gate:
            report.below_gate_skipped += 1
            continue
        scored.append((posting, result))

    # Maiores fit_score primeiro — o teto do ciclo prioriza as vagas mais aderentes.
    scored.sort(key=lambda pair: pair[1].total, reverse=True)

    to_process = scored[:max_jobs_per_cycle]
    report.deferred = max(len(scored) - len(to_process), 0)

    active_pipeline = pipeline or JobPipeline()
    for posting, score in to_process:
        try:
            outcome = adapt_and_ingest(
                posting,
                score,
                master_resume,
                pipeline=active_pipeline,
                generate_pdfs=generate_pdfs,
            )
            report.adapted.append(outcome["slug"])
        except IngestionError as exc:
            report.failed.append({"posting": f"{posting.company} - {posting.title}", "error": str(exc)})

    return report
