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


class _FlakySession:
    """Fake session que falha para os boards listados em `failing` e responde para o resto."""

    def __init__(self, payload_by_url_substring, failing):
        self._payloads = payload_by_url_substring
        self._failing = failing
        self.requested_urls = []

    def get(self, url, timeout=None):
        self.requested_urls.append(url)
        for bad in self._failing:
            if bad in url:
                raise RuntimeError(f"404 Client Error for {bad}")
        for substring, payload in self._payloads.items():
            if substring in url:
                return _FakeResponse(payload)
        raise AssertionError(f"Unexpected URL requested: {url}")


def test_greenhouse_bad_token_does_not_discard_the_other_boards():
    """Regressão: um slug errado no meio da lista derrubava a fonte inteira e as vagas
    já coletadas dos boards válidos iam junto — inaceitável com uma lista de slugs que
    ainda não foi verificada uma a uma."""
    payload = {"jobs": [{"id": 1, "title": "PMM", "location": "Remote", "absolute_url": "u"}]}
    session = _FlakySession({"boards/boa": payload}, failing=["boards/slug-errado"])
    source = GreenhouseSource(board_tokens=["slug-errado", "boa"], session=session)

    postings = source.discover()

    assert len(postings) == 1  # a vaga do board bom sobreviveu
    assert len(source.board_errors) == 1
    assert "slug-errado" in source.board_errors[0]


def test_discover_all_reports_individual_board_failures():
    """O slug errado não pode falhar em silêncio: sem isso ele fica indistinguível de
    'essa empresa não tem vaga aberta agora'."""
    payload = {"jobs": []}
    session = _FlakySession({"boards/boa": payload}, failing=["boards/slug-errado"])
    source = GreenhouseSource(board_tokens=["slug-errado", "boa"], session=session)

    _, errors = discover_all([source])

    assert len(errors) == 1
    assert errors[0].source_name == "greenhouse"
    assert "slug-errado" in errors[0].error


def test_greenhouse_uses_the_board_display_name_as_company():
    """`company` vira `metadata.company_name`, que é o nome que a carta precisa citar —
    gravar o slug cru ("gympass") produziria carta endereçada ao slug e desalinhada do
    nome real da empresa."""
    session = _FakeSession({
        "boards-api.greenhouse.io/v1/boards/gympass/jobs": {
            "jobs": [{"id": 1, "title": "GTM Manager", "location": "Brazil", "absolute_url": "u"}]
        },
        "boards-api.greenhouse.io/v1/boards/gympass": {"name": "Wellhub"},
    })
    source = GreenhouseSource(board_tokens=["gympass"], session=session)

    postings = source.discover()

    assert postings[0].company == "Wellhub"


def test_company_name_falls_back_to_prettified_slug_when_metadata_has_no_name():
    """Se os metadados do board não trouxerem o nome, o slug embelezado é melhor que
    o slug cru — "wildlife-studios" vira "Wildlife Studios", não fica assim na carta."""
    session = _FakeSession({
        "boards/wildlife-studios/jobs": {
            "jobs": [{"id": 1, "title": "X", "absolute_url": "u"}]
        },
        "boards/wildlife-studios": {},  # metadados sem a chave "name"
    })
    source = GreenhouseSource(board_tokens=["wildlife-studios"], session=session)

    postings = source.discover()

    assert postings[0].company == "Wildlife Studios"


def test_prettify_slug_handles_separators_and_empty():
    from engine.automation.radar import _prettify_slug

    assert _prettify_slug("wildlife-studios") == "Wildlife Studios"
    assert _prettify_slug("rd_station") == "Rd Station"
    assert _prettify_slug("ebanx") == "Ebanx"


def test_lever_bad_account_is_isolated():
    payload = [{"id": "x", "text": "Growth Lead", "categories": {}, "hostedUrl": "u"}]
    session = _FlakySession({"postings/boa": payload}, failing=["postings/ruim"])
    source = LeverSource(accounts=["ruim", "boa"], session=session)

    postings = source.discover()

    assert len(postings) == 1
    assert postings[0].company == "Boa"  # slug embelezado
    assert len(source.board_errors) == 1


def test_ashby_bad_board_is_isolated_and_uses_payload_name():
    session = _FlakySession(
        {"job-board/boa": {"name": "Empresa Boa", "jobs": [{"id": "1", "title": "AI Policy Lead"}]}},
        failing=["job-board/ruim"],
    )
    source = AshbySource(board_names=["ruim", "boa"], session=session)

    postings = source.discover()

    assert len(postings) == 1
    assert postings[0].company == "Empresa Boa"
    assert len(source.board_errors) == 1


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
