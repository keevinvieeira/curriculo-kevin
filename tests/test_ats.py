"""Tests for engine/application/ats.py — ATS platform detection from a posting URL."""
from __future__ import annotations

from engine.application.ats import detect_ats_platform, is_supported


def test_detects_greenhouse_board_url():
    assert detect_ats_platform("https://boards.greenhouse.io/acme/jobs/12345") == "greenhouse"


def test_detects_greenhouse_embedded_query_param():
    assert detect_ats_platform("https://acme.com/careers/apply?gh_jid=12345") == "greenhouse"


def test_detects_lever_url():
    assert detect_ats_platform("https://jobs.lever.co/acme/1a2b3c4d") == "lever"


def test_detects_ashby_url():
    assert detect_ats_platform("https://jobs.ashbyhq.com/acme/1a2b3c4d") == "ashby"


def test_unknown_url_returns_none():
    assert detect_ats_platform("https://linkedin.com/jobs/view/12345") is None
    assert is_supported("https://linkedin.com/jobs/view/12345") is False


def test_empty_url_returns_none():
    assert detect_ats_platform("") is None
