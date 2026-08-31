"""Tests for engine/application/answer_engine.py — the hierarchy that decides how
(or whether) to fill each form field. No real LLM calls: the LLM step is monkeypatched
via llm_client.generate_structured, same pattern as the rest of the test suite."""
from __future__ import annotations

import engine.application.answer_engine as answer_engine_module
from engine.application.answer_engine import resolve_answer
from engine.application.form_parser import FormField

_RESUME = {
    "name": "Kevin Augusto Vieira",
    "email": "kevin@example.com",
    "phone": "+55 41 90000-0000",
    "linkedin": "linkedin.com/in/kevin",
    "location": "Curitiba, Brasil",
}
_MASTER_RESUME = {
    "work_experience": [
        {"company": "Acme", "roles": [{"title": "GTM Program Manager"}]},
    ],
    "technical_skills": {"pt": [{"skills": ["Salesforce", "HubSpot", "SQL"]}]},
}


def _materials(form_answers=None):
    return {"cover_letter": "Carta.", "form_answers": form_answers or []}


def test_basic_field_resolved_from_resume_email():
    field = FormField(label="Email Address", field_type="text", name="email")
    result = resolve_answer(field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME)
    assert result.source == "resume_field"
    assert result.value == "kevin@example.com"


def test_basic_field_resolved_from_resume_linkedin():
    field = FormField(label="LinkedIn Profile URL", field_type="text", name="linkedin_url")
    result = resolve_answer(field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME)
    assert result.source == "resume_field"
    assert result.value == "linkedin.com/in/kevin"


def test_materials_match_above_threshold():
    field = FormField(label="Why are you interested in this company?", field_type="textarea", name="why")
    materials = _materials([
        {"question": "Why are you interested in this company?", "answer": "Porque admiro a missão."}
    ])
    result = resolve_answer(field, resume=_RESUME, materials=materials, master_resume=_MASTER_RESUME)
    assert result.source == "materials"
    assert result.value == "Porque admiro a missão."


def test_materials_no_match_falls_through_to_llm_or_human(monkeypatch):
    field = FormField(label="Totally unrelated obscure question about pets", field_type="textarea", name="pets")
    materials = _materials([{"question": "Why are you interested in this company?", "answer": "X"}])
    monkeypatch.setattr(answer_engine_module, "_try_llm_with_evidence", lambda *a, **k: None)
    result = resolve_answer(
        field, resume=_RESUME, materials=materials, master_resume=_MASTER_RESUME, use_llm=False
    )
    assert result.source == "human_required"


def test_checkbox_always_human_required():
    field = FormField(label="I agree to the terms", field_type="checkbox", name="consent")
    result = resolve_answer(field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME)
    assert result.source == "human_required"
    assert "consentimento" in result.reason.casefold() or "checkbox" in result.reason.casefold()


def test_select_field_without_confident_match_is_human_required():
    field = FormField(
        label="How did you hear about us?", field_type="select", name="source",
        options=["LinkedIn", "Referral", "Job Board"],
    )
    result = resolve_answer(field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME)
    assert result.source == "human_required"


def test_select_field_resolved_via_materials_and_option_matching():
    field = FormField(
        label="Are you willing to relocate?", field_type="select", name="relocate",
        options=["Yes", "No", "Maybe"],
    )
    materials = _materials([{"question": "Are you willing to relocate?", "answer": "Yes"}])
    result = resolve_answer(field, resume=_RESUME, materials=materials, master_resume=_MASTER_RESUME)
    assert result.source == "materials"
    assert result.value == "Yes"


def test_llm_with_grounded_evidence_is_accepted(monkeypatch):
    field = FormField(label="Describe your CRM experience", field_type="textarea", name="crm")

    class FakeAnswer:
        answer = "Trabalhei com Salesforce e HubSpot em operações de receita."
        evidence = ["Salesforce", "HubSpot"]

    monkeypatch.setattr(
        "llm_client.generate_structured", lambda schema, prompt, **kw: FakeAnswer()
    )

    result = resolve_answer(field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME)
    assert result.source == "llm_evidence"
    assert "Salesforce" in result.value


def test_llm_with_ungrounded_evidence_is_rejected(monkeypatch):
    field = FormField(label="Describe your CRM experience", field_type="textarea", name="crm")

    class FakeAnswer:
        answer = "Trabalhei com Marketo por 5 anos."
        evidence = ["Marketo"]  # not present anywhere in _MASTER_RESUME

    monkeypatch.setattr(
        "llm_client.generate_structured", lambda schema, prompt, **kw: FakeAnswer()
    )

    result = resolve_answer(field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME)
    assert result.source == "human_required"
    assert "marketo" in result.reason.casefold()


def test_llm_empty_answer_is_human_required(monkeypatch):
    field = FormField(label="Describe your experience with quantum computing", field_type="textarea", name="qc")

    class FakeAnswer:
        answer = ""
        evidence = []

    monkeypatch.setattr(
        "llm_client.generate_structured", lambda schema, prompt, **kw: FakeAnswer()
    )

    result = resolve_answer(field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME)
    assert result.source == "human_required"


def test_use_llm_false_skips_llm_entirely():
    field = FormField(label="Describe your CRM experience", field_type="textarea", name="crm")
    result = resolve_answer(
        field, resume=_RESUME, materials=_materials(), master_resume=_MASTER_RESUME, use_llm=False
    )
    assert result.source == "human_required"
