"""HTTP-level integration test for llm_client.py against a *stub* OpenRouter server.

Everything else in this suite mocks at the Python level (`generate_structured` or
`instructor.from_provider` get monkeypatched), which proves the call sites are wired
up but never exercises the actual HTTP request `instructor` + `openai` build, nor the
parsing of a real OpenRouter-shaped response back into a Pydantic model. A wrong
`base_url`, a missing auth header, a mis-serialized tool schema, or an
instructor-version incompatibility would all slip through those mocks.

This test closes that gap without network access: it starts a real HTTP server on
localhost that speaks the OpenAI-compatible chat-completions API (which is what
OpenRouter exposes), points the client at it via the `base_url` override, and asserts
on both directions of the exchange — what actually went out on the wire, and that
what came back was validated into the expected model.

It does NOT prove the real OpenRouter accepts our requests (only a live call with a
real key can, see `scripts/verify_openrouter.py`) — but it does prove everything on
this side of the wire is correct.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pydantic import BaseModel, Field

import llm_client

pytest.importorskip("instructor")
pytest.importorskip("openai")


class ResumeSummary(BaseModel):
    """Stand-in for the project's real schemas (AdaptedResume, JobMaterials, ...)."""

    name: str = Field(description="Candidate name")
    headline: str = Field(description="One-line professional headline")
    years_experience: int = Field(description="Total years of experience")


CANNED_ANSWER = {
    "name": "Kevin Augusto Vieira",
    "headline": "GTM & Revenue Operations",
    "years_experience": 8,
}


class _StubOpenRouterHandler(BaseHTTPRequestHandler):
    """Minimal OpenAI-compatible /chat/completions endpoint."""

    received_requests: list = []

    def do_POST(self):  # noqa: N802 - name mandated by BaseHTTPRequestHandler
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length)
        body = json.loads(raw_body) if raw_body else {}
        type(self).received_requests.append(
            {"path": self.path, "headers": dict(self.headers), "body": body}
        )

        # instructor (Mode.TOOLS) names the function after the response_model.
        tool_name = ResumeSummary.__name__
        tools = body.get("tools") or []
        if tools:
            tool_name = tools[0].get("function", {}).get("name", tool_name)

        response = {
            "id": "chatcmpl-stub-1",
            "object": "chat.completion",
            "created": 1,
            "model": body.get("model", "stub-model"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_stub_1",
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": json.dumps(CANNED_ANSWER),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        }
        payload = json.dumps(response).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silence per-request stderr logging
        return


@pytest.fixture
def stub_openrouter():
    _StubOpenRouterHandler.received_requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubOpenRouterHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    try:
        yield f"http://{host}:{port}/api/v1", _StubOpenRouterHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_generate_structured_round_trips_over_real_http(stub_openrouter):
    base_url, handler = stub_openrouter

    result = llm_client.generate_structured(
        ResumeSummary,
        "Resuma o perfil do candidato.",
        temperature=0.2,
        api_key="test-key-123",
        model="anthropic/claude-opus-5",
        base_url=base_url,
    )

    # 1. The response really was parsed and validated into the Pydantic model.
    assert isinstance(result, ResumeSummary)
    assert result.name == CANNED_ANSWER["name"]
    assert result.years_experience == 8

    # 2. Exactly one HTTP request went out, to the chat-completions path.
    assert len(handler.received_requests) == 1
    request = handler.received_requests[0]
    assert request["path"].endswith("/chat/completions")


def test_request_carries_auth_header_model_and_prompt(stub_openrouter):
    base_url, handler = stub_openrouter

    llm_client.generate_structured(
        ResumeSummary,
        "Prompt específico da vaga XPTO.",
        temperature=0.1,
        api_key="test-key-123",
        model="anthropic/claude-opus-5",
        base_url=base_url,
    )

    request = handler.received_requests[0]
    assert request["headers"].get("Authorization") == "Bearer test-key-123"
    assert request["body"]["model"] == "anthropic/claude-opus-5"
    assert request["body"]["temperature"] == 0.1
    assert any(
        "XPTO" in (message.get("content") or "")
        for message in request["body"]["messages"]
    )


def test_request_sends_the_response_model_as_a_tool_schema(stub_openrouter):
    """The schema instructor sends is what forces structured output — if this ever
    stops being sent (e.g. an instructor API change), the zero-hallucination
    guarantees that depend on validated models would silently degrade."""
    base_url, handler = stub_openrouter

    llm_client.generate_structured(
        ResumeSummary, "Prompt.", api_key="test-key-123", base_url=base_url
    )

    body = handler.received_requests[0]["body"]
    tools = body.get("tools") or []
    assert tools, "nenhum schema de ferramenta foi enviado — saída estruturada não está garantida"
    function_schema = tools[0]["function"]
    properties = function_schema["parameters"]["properties"]
    assert set(properties) == {"name", "headline", "years_experience"}


def test_base_url_falls_back_to_env_var_then_openrouter(monkeypatch):
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)
    assert llm_client.resolve_base_url() == llm_client.OPENROUTER_BASE_URL

    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://gateway.example/api/v1")
    assert llm_client.resolve_base_url() == "https://gateway.example/api/v1"
    # An explicit argument still wins over the env var.
    assert llm_client.resolve_base_url("http://127.0.0.1:9/api/v1") == "http://127.0.0.1:9/api/v1"
