"""Tests for the Gemini -> OpenRouter migration (llm_client.py + utils.py call sites).

These tests never hit the network: instructor.from_provider is monkeypatched with a
fake client whose .create() just returns a pre-built instance of whatever
response_model was requested. That's enough to prove the plumbing (env var handling,
error messages, prompt construction, return type) is correct without needing a real
OPENROUTER_API_KEY.
"""
from __future__ import annotations

import pytest

import llm_client


class _FakeLLMClient:
    """Stand-in for instructor.from_provider(...) — records calls, returns canned models."""

    def __init__(self, canned_response):
        self.canned_response = canned_response
        self.last_call = None

    def create(self, *, messages, response_model, temperature):
        self.last_call = {
            "messages": messages,
            "response_model": response_model,
            "temperature": temperature,
        }
        return self.canned_response


def test_get_llm_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenRouter API Key"):
        llm_client.get_llm_client(api_key=None)


def test_get_llm_client_uses_default_model(monkeypatch):
    captured = {}

    def fake_from_provider(model_string, **kwargs):
        captured["model_string"] = model_string
        captured["kwargs"] = kwargs
        return _FakeLLMClient(canned_response=None)

    monkeypatch.setattr(llm_client.instructor, "from_provider", fake_from_provider)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    llm_client.get_llm_client(api_key="test-key")

    assert captured["model_string"] == f"openrouter/{llm_client.DEFAULT_MODEL}"
    assert captured["kwargs"]["api_key"] == "test-key"
    assert captured["kwargs"]["base_url"] == llm_client.OPENROUTER_BASE_URL


def test_get_llm_client_respects_model_override(monkeypatch):
    captured = {}

    def fake_from_provider(model_string, **kwargs):
        captured["model_string"] = model_string
        return _FakeLLMClient(canned_response=None)

    monkeypatch.setattr(llm_client.instructor, "from_provider", fake_from_provider)
    monkeypatch.setenv("OPENROUTER_MODEL", "google/gemini-3.5-flash-lite")

    llm_client.get_llm_client(api_key="test-key")

    assert captured["model_string"] == "openrouter/google/gemini-3.5-flash-lite"


def test_generate_structured_returns_model_instance(monkeypatch):
    from pydantic import BaseModel

    class Dummy(BaseModel):
        value: str

    fake = _FakeLLMClient(canned_response=Dummy(value="ok"))
    monkeypatch.setattr(
        llm_client, "get_llm_client", lambda api_key=None, model=None, base_url=None: fake
    )

    result = llm_client.generate_structured(Dummy, "some prompt", temperature=0.4)

    assert isinstance(result, Dummy)
    assert result.value == "ok"
    assert fake.last_call["temperature"] == 0.4
    assert fake.last_call["response_model"] is Dummy


def test_adapt_resume_with_llm_calls_generate_structured(monkeypatch):
    import utils

    sentinel = object()
    captured = {}

    def fake_generate_structured(response_model, prompt, *, temperature, api_key=None, model=None):
        captured["response_model"] = response_model
        captured["temperature"] = temperature
        captured["prompt"] = prompt
        return sentinel

    monkeypatch.setattr(utils, "generate_structured", fake_generate_structured)

    result = utils.adapt_resume_with_llm(
        master_resume={"technical_skills": {}},
        job_description="Vaga de teste",
        target_lang="pt",
    )

    assert result is sentinel
    assert captured["response_model"] is utils.AdaptedResume
    assert captured["temperature"] == 0.2
    assert "Vaga de teste" in captured["prompt"]


def test_generate_job_materials_calls_generate_structured(monkeypatch):
    import utils

    sentinel = object()
    captured = {}

    def fake_generate_structured(response_model, prompt, *, temperature, api_key=None, model=None):
        captured["response_model"] = response_model
        captured["temperature"] = temperature
        return sentinel

    monkeypatch.setattr(utils, "generate_structured", fake_generate_structured)

    result = utils.generate_job_materials(
        master_resume={"technical_skills": {}},
        job_description="Vaga de teste",
        target_lang="en",
    )

    assert result is sentinel
    assert captured["response_model"] is utils.JobMaterials
    assert captured["temperature"] == 0.3
