"""Shared LLM client for Career OS — OpenRouter backend.

Historically this project called the Gemini API directly (via `google-genai`) in two
places: `utils.py` (resume/materials generation) and `engine/job_parser.py` (job
description parsing for the Knowledge Graph). Both now go through OpenRouter instead,
using the `instructor` library so callers keep getting back validated Pydantic models
(`AdaptedResume`, `JobMaterials`, `ParsedJobPosting`, `JobTriples`, ...) exactly like
before — only the provider underneath changed.

Why OpenRouter: one API key/gateway in front of many providers, instead of a hard
dependency on a single vendor's SDK. The model actually used is configurable via the
OPENROUTER_MODEL environment variable, so switching models later never requires a
code change.

Default model: `anthropic/claude-opus-5`. Picked because (checked directly against
OpenRouter's live model catalog on 2026-08-31) it supports `structured_outputs` and
`tool_choice`, and Anthropic models are consistently strong at following rigid
constraints like "never invent experience" — the central rule of this project. This
project's LLM call volume is intentionally low (see the per-cycle cap in
engine/automation/workflow.py), so the higher per-call cost of a top-tier model is
bounded. For a cheaper default, set OPENROUTER_MODEL to e.g. "google/gemini-3.5-flash-lite"
(also confirmed structured_outputs on OpenRouter, a small fraction of the cost).

Always re-check https://openrouter.ai/models?supported_parameters=structured_outputs
before relying on a specific model id — OpenRouter's catalog and per-endpoint support
change over time, and today's model may be renamed or retired later.
"""
from __future__ import annotations

import os
from typing import Any, Optional, Type, TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel

try:
    import instructor
except Exception:  # pragma: no cover - exercised only when the package is missing
    instructor = None

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-opus-5"

T = TypeVar("T", bound=BaseModel)


def resolve_base_url(base_url: Optional[str] = None) -> str:
    """Base URL for the OpenAI-compatible endpoint, in precedence order:
    explicit argument > OPENROUTER_BASE_URL env var > OpenRouter's own URL.

    The override exists for two real cases: pointing at a corporate gateway/proxy that
    speaks the same API, and pointing the test suite at a local stub server so the
    HTTP wiring itself can be exercised offline (see tests/test_llm_client_http.py).
    """
    return base_url or os.getenv("OPENROUTER_BASE_URL") or OPENROUTER_BASE_URL


def get_llm_client(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Any:
    """Return an instructor-patched client wired to OpenRouter.

    Raises RuntimeError if `instructor` isn't installed, or ValueError if no API key
    is available — mirrors the previous get_client() behaviour in utils.py so callers
    (and their error handling / Streamlit messages) don't need to change.
    """
    if instructor is None:
        raise RuntimeError(
            "O pacote 'instructor' não está instalado neste ambiente. "
            "Rode: pip install instructor openai"
        )
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError(
            "OpenRouter API Key não encontrada. Defina OPENROUTER_API_KEY no ambiente, "
            "no arquivo .env, ou informe explicitamente ao chamar esta função."
        )
    resolved_model = model or os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    return instructor.from_provider(
        f"openrouter/{resolved_model}",
        base_url=resolve_base_url(base_url),
        api_key=key,
        async_client=False,
    )


def generate_structured(
    response_model: Type[T],
    prompt: str,
    *,
    temperature: float = 0.2,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> T:
    """Run a single-turn structured-output completion, returning a validated Pydantic model.

    Thin wrapper so call sites (utils.py, engine/job_parser.py) don't each re-implement
    client construction + error handling.
    """
    client = get_llm_client(api_key=api_key, model=model, base_url=base_url)
    return client.create(
        messages=[{"role": "user", "content": prompt}],
        response_model=response_model,
        temperature=temperature,
    )
