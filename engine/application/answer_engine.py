"""Resolves one FormField into an answer, following the hierarchy from the plan:

    1. Basic profile fields (name/email/phone/linkedin/github/website/location) —
       pulled directly and deterministically from the already-adapted résumé. No
       matching involved: these are exact, structured fields.
    2. JobMaterials.form_answers — label-similarity match (rapidfuzz) against the
       pre-generated Q&A pairs for this job, above `similarity_threshold`.
    3. LLM with evidence — only for free-text fields (select/radio/checkbox never
       reach this step, see below), and only accepted if every piece of "evidence" the
       model cites is a literal substring of the master résumé. Any ungrounded
       evidence, or an empty answer, is discarded outright — never partially trusted.
    4. HUMAN_REQUIRED — the field is left for the person to fill in Streamlit's
       review screen (Fase 5/6). This is also the *only* outcome for every checkbox
       (never auto-check consent/legal/EEO boxes) and for select/radio fields once
       steps 1-2 don't produce a confident match (no LLM guessing at multiple-choice
       answers — picking the wrong option silently is worse than leaving it blank).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rapidfuzz import fuzz

from engine.application.form_parser import FormField

SIMILARITY_THRESHOLD_DEFAULT = 72.0  # rapidfuzz score, 0-100

_BASIC_FIELD_KEYWORDS = {
    "name": ("full name", "your name", "nome completo", "nome"),
    "email": ("email", "e-mail"),
    "phone": ("phone", "telefone", "celular", "mobile"),
    "linkedin": ("linkedin",),
    "github": ("github",),
    "website": ("website", "portfolio", "portfólio", "site pessoal"),
    "location": ("location", "localização", "cidade", "city", "endereço"),
}


@dataclass
class AnswerResult:
    field: FormField
    value: Optional[str]
    source: str  # "resume_field" | "materials" | "llm_evidence" | "human_required"
    confidence: Optional[float] = None
    evidence: Optional[List[str]] = None
    reason: Optional[str] = None  # why it fell through to HUMAN_REQUIRED, if it did


def _human_required(field: FormField, reason: str) -> AnswerResult:
    return AnswerResult(field=field, value=None, source="human_required", reason=reason)


def _match_basic_field(label: str, resume: Dict[str, Any]) -> Optional[AnswerResult]:
    label_cf = label.casefold()
    for resume_key, keywords in _BASIC_FIELD_KEYWORDS.items():
        if any(keyword in label_cf for keyword in keywords):
            value = resume.get(resume_key)
            if value:
                return AnswerResult(field=None, value=value, source="resume_field", confidence=100.0)
    return None


def _best_materials_match(
    label: str, form_answers: List[Dict[str, str]], threshold: float
) -> Optional[AnswerResult]:
    best_score = 0.0
    best_answer = None
    for entry in form_answers:
        question = entry.get("question", "")
        score = fuzz.token_set_ratio(label, question)
        if score > best_score:
            best_score = score
            best_answer = entry.get("answer")
    if best_answer and best_score >= threshold:
        return AnswerResult(field=None, value=best_answer, source="materials", confidence=best_score)
    return None


def _flatten_master_resume(master_resume: Dict[str, Any]) -> str:
    return json.dumps(master_resume, ensure_ascii=False).casefold()


def _try_llm_with_evidence(
    field: FormField,
    master_resume: Dict[str, Any],
    *,
    api_key: Optional[str],
    model: Optional[str],
) -> Optional[AnswerResult]:
    try:
        from llm_client import generate_structured
        from pydantic import BaseModel, Field
    except Exception:
        return None

    class GroundedAnswer(BaseModel):
        answer: str = Field(
            description=(
                "Answer to the form question using ONLY facts literally present in the "
                "provided master résumé. Empty string if it can't be answered this way."
            )
        )
        evidence: List[str] = Field(
            default_factory=list,
            description="Literal substrings copied from the master résumé that support the answer.",
        )

    prompt = (
        "Job application form question:\n"
        f"{field.label}\n\n"
        "Candidate's master résumé (JSON, the only allowed source of facts):\n"
        f"{json.dumps(master_resume, ensure_ascii=False)}\n\n"
        "Answer the question using only facts literally present above. Never invent "
        "experience, skills, or numbers. If the résumé doesn't support a real answer, "
        "return an empty answer and an empty evidence list."
    )

    try:
        result = generate_structured(GroundedAnswer, prompt, temperature=0.1, api_key=api_key, model=model)
    except Exception as exc:  # noqa: BLE001 - any LLM failure just falls through to HUMAN_REQUIRED
        return _human_required(field, f"Falha ao consultar LLM: {exc}")

    if not result.answer.strip():
        return _human_required(field, "LLM não encontrou base real no currículo mestre para responder.")

    resume_blob = _flatten_master_resume(master_resume)
    for evidence_item in result.evidence:
        if evidence_item.casefold() not in resume_blob:
            return _human_required(
                field,
                f"Evidência citada pela LLM não existe literalmente no currículo mestre: {evidence_item!r}",
            )

    return AnswerResult(
        field=field, value=result.answer, source="llm_evidence", evidence=result.evidence
    )


def resolve_answer(
    field: FormField,
    *,
    resume: Dict[str, Any],
    materials: Dict[str, Any],
    master_resume: Dict[str, Any],
    similarity_threshold: float = SIMILARITY_THRESHOLD_DEFAULT,
    use_llm: bool = True,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> AnswerResult:
    """Resolve a single FormField following the hierarchy documented at module level.

    `resume` / `materials` are the plain dicts already stored on the job artifact
    (`job["resume"][lang]`, `job["materials"][lang]`) — not the Pydantic models,
    since this runs after they've already been through `.model_dump()`.
    """
    if field.field_type == "checkbox":
        return _human_required(field, "Checkboxes (consentimento/legal/EEO) sempre exigem revisão humana.")

    basic_match = _match_basic_field(field.label, resume)
    if basic_match:
        basic_match.field = field
        return basic_match

    materials_match = _best_materials_match(
        field.label, materials.get("form_answers", []), similarity_threshold
    )
    if materials_match:
        materials_match.field = field
        if field.field_type in ("select", "radio") and field.options:
            picked = _pick_closest_option(materials_match.value, field.options, similarity_threshold)
            if picked is None:
                return _human_required(
                    field,
                    "Resposta encontrada em form_answers não corresponde com confiança "
                    "a nenhuma opção disponível no campo.",
                )
            materials_match.value = picked
        return materials_match

    if field.field_type in ("select", "radio"):
        return _human_required(
            field, "Nenhuma correspondência confiável em form_answers para um campo de escolha única."
        )

    if use_llm:
        llm_result = _try_llm_with_evidence(field, master_resume, api_key=api_key, model=model)
        if llm_result is not None:
            return llm_result

    return _human_required(field, "Nenhuma fonte determinística resolveu este campo.")


def _pick_closest_option(answer_text: str, options: List[str], threshold: float) -> Optional[str]:
    best_score = 0.0
    best_option = None
    for option in options:
        score = fuzz.token_set_ratio(answer_text, option)
        if score > best_score:
            best_score = score
            best_option = option
    if best_option and best_score >= threshold:
        return best_option
    return None
