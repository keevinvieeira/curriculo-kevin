"""Tests for engine/automation/radar.py — never hits the network.

requests.Session.get is monkeypatched with fake responses shaped like real
Greenhouse/Lever payloads (see the module docstring for which fields were verified
live vs. best-effort).
"""
from __future__ import annotations

from engine.automation.radar import (
    AshbySource,
    CustomSource,
    GreenhouseSource,
    LeverSource,
    RawJobPosting,
    discover_all,
)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload_by_url_substring):
        self._payloads = payload_by_url_substring
        self.requested_urls = []

    def get(self, url, timeout=None):
        self.requested_urls.append(url)
        for substring, payload in self._payloads.items():
            if substring in url:
                return _FakeResponse(payload)
        raise AssertionError(f"Unexpected URL requested: {url}")


def test_greenhouse_source_parses_confirmed_fields():
    payload = {
        "jobs": [
            {
                "id": 6789012,
                "title": "Senior Product Marketing Manager",
                "updated_at": "2026-08-20T10:00:00Z",
                "location": {"name": "Remote - Brazil"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/6789012",
                "content": "<p>Own GTM for our AI product line.</p>",
                "departments": [{"name": "Marketing"}],
            }
        ]
    }
    session = _FakeSession({"boards-api.greenhouse.io/v1/boards/acme": payload})
    source = GreenhouseSource(board_tokens=["acme"], session=session)

    postings = source.discover()

    assert len(postings) == 1
    posting = postings[0]
    assert isinstance(posting, RawJobPosting)
    assert posting.title == "Senior Product Marketing Manager"
    assert posting.location == "Remote - Brazil"
    assert posting.url == "https://boards.greenhouse.io/acme/jobs/6789012"
    assert posting.source == "greenhouse"
    assert posting.source_id == "6789012"


def test_greenhouse_source_handles_string_location():
    payload = {"jobs": [{"id": 1, "title": "X", "location": "São Paulo", "absolute_url": "u"}]}
    session = _FakeSession({"boards-api.greenhouse.io": payload})
    source = GreenhouseSource(board_tokens=["acme"], session=session)

    postings = source.discover()

    assert postings[0].location == "São Paulo"


def test_lever_source_parses_confirmed_fields():
    payload = [
        {
            "id": "1a2b3c4d-1a2b-1a2b-1a2b-1a2b3c4d5e6f",
            "text": "Growth Marketing Manager",
            "categories": {"location": "Brazil - Remote", "commitment": "Full-time"},
            "hostedUrl": "https://jobs.lever.co/acme/1a2b3c4d-1a2b-1a2b-1a2b-1a2b3c4d5e6f",
            "createdAt": 1755600000000,  # ms epoch
            "workplaceType": "remote",
            "descriptionPlain": "Own growth and acquisition.",
        }
    ]
    session = _FakeSession({"api.lever.co/v0/postings/acme": payload})
    source = LeverSource(accounts=["acme"], session=session)

    postings = source.discover()

    assert len(postings) == 1
    posting = postings[0]
    assert posting.title == "Growth Marketing Manager"
    assert posting.location == "Brazil - Remote"
    assert posting.remote is True
    assert posting.employment_type == "Full-time"
    assert posting.posted_at is not None
    assert posting.source_id == "1a2b3c4d-1a2b-1a2b-1a2b-1a2b3c4d5e6f"


def test_ashby_source_falls_back_across_key_names():
    payload = {
        "jobs": [
            {
                "id": "abc123",
                "title": "AI Governance Lead",
                "applyUrl": "https://jobs.ashbyhq.com/acme/abc123",
                "locationName": "Remote",
                "isRemote": True,
                "createdAt": "2026-08-15T00:00:00Z",
                "description": "Shape our AI governance policy.",
            }
        ]
    }
    session = _FakeSession({"api.ashbyhq.com/posting-api/job-board/acme": payload})
    source = AshbySource(board_names=["acme"], session=session)

    postings = source.discover()

    assert len(postings) == 1
    posting = postings[0]
    assert posting.title == "AI Governance Lead"
    assert posting.url == "https://jobs.ashbyhq.com/acme/abc123"
    assert posting.location == "Remote"
    assert posting.remote is True
    assert posting.posted_at == "2026-08-15T00:00:00Z"


def test_discover_all_isolates_source_failures():
    good_source = CustomSource("good", lambda: [RawJobPosting(company="X", title="Y", url="z")])

    def _boom():
        raise RuntimeError("API is down")

    bad_source = CustomSource("bad", _boom)

    postings, errors = discover_all([good_source, bad_source])

    assert len(postings) == 1
    assert len(errors) == 1
    assert errors[0].source_name == "bad"
    assert "API is down" in errors[0].error
