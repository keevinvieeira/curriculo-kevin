"""Tests for engine/automation/dedupe.py."""
from __future__ import annotations

from engine.automation.dedupe import (
    extract_ats_id,
    find_duplicate,
    normalize_url,
    token_overlap,
)


def test_normalize_url_strips_tracking_params_and_trailing_slash():
    a = normalize_url("https://Boards.greenhouse.io/Acme/jobs/12345/?utm_source=linkedin&ref=xyz")
    b = normalize_url("https://boards.greenhouse.io/acme/jobs/12345")
    assert a == b


def test_extract_ats_id_greenhouse():
    assert extract_ats_id("https://boards.greenhouse.io/acme/jobs/6789012") == "6789012"
    assert extract_ats_id("https://acme.com/apply?gh_jid=6789012") == "6789012"


def test_extract_ats_id_lever():
    url = "https://jobs.lever.co/acme/1a2b3c4d-1a2b-1a2b-1a2b-1a2b3c4d5e6f"
    assert extract_ats_id(url) == "1a2b3c4d-1a2b-1a2b-1a2b-1a2b3c4d5e6f"


def test_extract_ats_id_unknown_returns_none():
    assert extract_ats_id("https://example.com/careers/some-role") is None


def test_token_overlap_identical_is_one():
    assert token_overlap("Product Marketing Manager", "Product Marketing Manager") == 1.0


def test_token_overlap_partial():
    score = token_overlap("Senior Product Marketing Manager", "Product Marketing Manager, AI")
    assert 0.4 < score < 1.0


def test_find_duplicate_by_normalized_url():
    existing_jobs = [
        {
            "id": "acme-pmm",
            "metadata": {
                "url": "https://boards.greenhouse.io/acme/jobs/999?utm_source=x",
                "company_name": "Acme",
                "role_title": "Product Marketing Manager",
            },
        }
    ]
    match = find_duplicate(
        url="https://boards.greenhouse.io/acme/jobs/999",
        company="Acme Corp",
        role="Totally Different Title",
        existing_jobs=existing_jobs,
        existing_applications=[],
    )
    assert match == "acme-pmm"


def test_find_duplicate_by_company_and_role_overlap():
    existing_applications = [
        {
            "id": "42",
            "source_job_id": "acme-growth",
            "url": "https://example.com/old-link-that-changed",
            "company": "Acme Corporation",
            "role": "Senior Growth Marketing Manager",
        }
    ]
    match = find_duplicate(
        url="https://different-domain.example/careers/growth-role",
        company="Acme Corporation",
        role="Growth Marketing Manager",
        existing_jobs=[],
        existing_applications=existing_applications,
    )
    assert match == "acme-growth"


def test_find_duplicate_returns_none_for_genuinely_new_job():
    existing_jobs = [
        {
            "id": "other-co-pmm",
            "metadata": {
                "url": "https://boards.greenhouse.io/otherco/jobs/1",
                "company_name": "Other Co",
                "role_title": "Product Marketing Manager",
            },
        }
    ]
    match = find_duplicate(
        url="https://boards.greenhouse.io/brandnew/jobs/2",
        company="Brand New Co",
        role="AI Governance Lead",
        existing_jobs=existing_jobs,
        existing_applications=[],
    )
    assert match is None
