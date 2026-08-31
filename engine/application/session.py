"""Orchestrates one Application Prep Agent run for a single job: gate check ->
open the posting -> extract fields -> resolve answers -> fill the form -> stop.

Hard rule, enforced structurally, not just by convention: nothing in this module (or
anything it calls) ever clicks a submit/send button. The agent's job ends the moment
every resolvable field is filled; a human reviews the result in Streamlit (the fields
this module marks `human_required`, plus a final look at everything else) before the
posting is ever actually submitted — that's Fase 6's separate, later gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from engine.application.answer_engine import AnswerResult, resolve_answer
from engine.application.ats import detect_ats_platform
from engine.application.form_parser import FormField, extract_form_fields
from engine.automation.state_machine import (
    InvalidTransitionError,
    WorkflowStatus,
    get_workflow_status,
    transition,
)

_RESUME_FILE_KEYWORDS = ("resume", "cv", "currículo", "curriculo")


class UnsupportedAtsError(Exception):
    """Raised when the job's URL isn't a Greenhouse/Lever/Ashby posting (v1 scope)."""


@dataclass
class FilledField:
    label: str
    field_type: str
    value: Optional[str]
    source: str
    confidence: Optional[float] = None


@dataclass
class ApplicationSession:
    job_id: str
    url: str
    ats_platform: Optional[str]
    filled: List[FilledField] = field(default_factory=list)
    human_required: List[FilledField] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "ats_platform": self.ats_platform,
            "filled": [vars(f) for f in self.filled],
            "human_required": [vars(f) for f in self.human_required],
        }


def fill_application_form(
    page,
    job: Dict[str, Any],
    master_resume: Dict[str, Any],
    *,
    lang: str = "pt",
    resume_pdf_path: Optional[Path] = None,
    use_llm: bool = True,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> ApplicationSession:
    """Extract every field on `page` (already navigated to the application form) and
    fill in whatever answer_engine can resolve with confidence. Never touches any
    submit/send button."""
    metadata = job.get("metadata", {})
    url = metadata.get("url", "")
    ats_platform = detect_ats_platform(url)
    session = ApplicationSession(job_id=job["id"], url=url, ats_platform=ats_platform)

    resume = job.get("resume", {}).get(lang, {})
    materials = job.get("materials", {}).get(lang, {})

    for form_field in extract_form_fields(page):
        if form_field.field_type == "file":
            _handle_file_field(form_field, session, resume_pdf_path)
            continue

        result = resolve_answer(
            form_field,
            resume=resume,
            materials=materials,
            master_resume=master_resume,
            use_llm=use_llm,
            api_key=api_key,
            model=model,
        )
        _apply_result(page, result, session)

    return session


def _handle_file_field(
    form_field: FormField, session: ApplicationSession, resume_pdf_path: Optional[Path]
) -> None:
    label_cf = form_field.label.casefold()
    if resume_pdf_path and any(keyword in label_cf for keyword in _RESUME_FILE_KEYWORDS):
        form_field.locator.set_input_files(str(resume_pdf_path))
        session.filled.append(
            FilledField(
                label=form_field.label, field_type="file",
                value=str(resume_pdf_path), source="resume_pdf",
            )
        )
        return
    session.human_required.append(
        FilledField(label=form_field.label, field_type="file", value=None, source="human_required")
    )


def _apply_result(page, result: AnswerResult, session: ApplicationSession) -> None:
    form_field = result.field
    if result.source == "human_required":
        session.human_required.append(
            FilledField(
                label=form_field.label, field_type=form_field.field_type,
                value=None, source="human_required",
            )
        )
        return

    if form_field.field_type in ("text", "textarea"):
        form_field.locator.fill(result.value)
    elif form_field.field_type == "select":
        form_field.locator.select_option(label=result.value)
    elif form_field.field_type == "radio" and result.value in form_field.options:
        option_index = form_field.options.index(result.value)
        radios = page.query_selector_all(f'input[type="radio"][name="{form_field.name}"]')
        if option_index < len(radios):
            radios[option_index].check()

    session.filled.append(
        FilledField(
            label=form_field.label, field_type=form_field.field_type,
            value=result.value, source=result.source, confidence=result.confidence,
        )
    )


def run_application_prep(
    job: Dict[str, Any],
    master_resume: Dict[str, Any],
    *,
    page_factory: Callable[[], Any],
    lang: str = "pt",
    resume_pdf_path: Optional[Path] = None,
    use_llm: bool = True,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> ApplicationSession:
    """Full Fase 5 flow for one job: gate check -> transition(APPLICATION_PREPARING)
    -> fill what can be filled -> transition to AWAITING_APPLICATION_REVIEW with the
    session summary attached to job["automation"]["application_session"].

    `page_factory` is a zero-arg callable returning a Playwright Page already
    navigated to the job's application form — dependency-injected so tests never
    need a real browser hitting a real ATS site, and so the caller controls
    headless mode / persistent context / any login the real run needs.

    Raises InvalidTransitionError if the job isn't RESUME_APPROVED, and
    UnsupportedAtsError if its URL isn't one of the three supported ATS. Any failure
    while filling moves the job to BLOCKED (not FAILED — this isn't necessarily
    retryable the same way, it might need a human to look at the actual page) with
    the error recorded, and re-raises.
    """
    current_status = get_workflow_status(job)
    if current_status != WorkflowStatus.RESUME_APPROVED:
        raise InvalidTransitionError(
            "Application Prep Agent só pode rodar a partir de RESUME_APPROVED "
            f"(status atual: {current_status.value if current_status else 'sem automation'})."
        )

    url = job.get("metadata", {}).get("url", "")
    if not detect_ats_platform(url):
        raise UnsupportedAtsError(f"URL não é de um ATS suportado (Greenhouse/Lever/Ashby): {url!r}")

    transition(job, WorkflowStatus.APPLICATION_PREPARING)

    try:
        page = page_factory()
        session = fill_application_form(
            page, job, master_resume,
            lang=lang, resume_pdf_path=resume_pdf_path,
            use_llm=use_llm, api_key=api_key, model=model,
        )
    except Exception as exc:  # noqa: BLE001 - any failure here is a real BLOCKED state, not a crash
        transition(job, WorkflowStatus.BLOCKED)
        job["automation"]["last_error"] = str(exc)
        raise

    job.setdefault("automation", {})["application_session"] = session.to_dict()
    transition(job, WorkflowStatus.AWAITING_APPLICATION_REVIEW)
    return session
