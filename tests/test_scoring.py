"""Tests for engine/automation/scoring.py — the deterministic fit_score gate."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from engine.automation.scoring import score_job


def test_strong_match_brazil_remote_recent_passes_gate():
    result = score_job(
        title="Senior Product Marketing Manager, AI Governance",
        description=(
            "We're hiring a Product Marketing lead to own GTM strategy for our "
            "Responsible AI and AI Governance product line, working closely with "
            "Trust & Safety."
        ),
        location="Remote - Brazil",
        remote=True,
        salary_range="R$ 20.000 - R$ 28.000",
        posted_at=(datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
        min_salary_expected=15000,
    )
    assert result.total >= 80
    assert result.passes_gate
    assert not result.hard_blockers
    assert "Product Marketing" in result.matched_categories


def test_irrelevant_role_scores_low_and_fails_gate():
    result = score_job(
        title="Warehouse Forklift Operator",
        description="Operate forklifts and manage inventory in our distribution center.",
        location="Ohio, USA (on-site)",
        remote=False,
    )
    assert result.total < 80
    assert not result.passes_gate
    assert result.matched_categories == []


def test_hard_blocker_fails_gate_even_with_high_category_match():
    result = score_job(
        title="AI Governance Product Marketing Lead",
        description=(
            "Own GTM and product marketing strategy for our AI governance and "
            "responsible AI initiatives. US Citizens only. Security clearance required."
        ),
        location="Remote - Brazil",
        remote=True,
    )
    assert result.hard_blockers  # blockers present
    assert not result.passes_gate  # regardless of the numeric score


def test_missing_salary_and_recency_give_partial_neutral_credit():
    result = score_job(
        title="Growth Marketing Manager",
        description="Own growth and acquisition strategy for our GTM team.",
        location="",
        remote=None,
        salary_range=None,
        posted_at=None,
    )
    assert 0 < result.breakdown["salary"] < 15
    assert 0 < result.breakdown["recency"] < 10


def test_stale_posting_scores_zero_recency():
    result = score_job(
        title="Growth Marketing Manager",
        description="Own growth and acquisition strategy.",
        posted_at=(datetime.now(timezone.utc) - timedelta(days=120)).isoformat(),
    )
    assert result.breakdown["recency"] == 0


def test_breakdown_sums_to_total():
    result = score_job(
        title="AI Ethics Policy Lead",
        description="Shape AI ethics and responsible AI governance policy.",
        location="São Paulo, Brasil",
        salary_range="R$ 18.000",
        posted_at=datetime.now(timezone.utc).isoformat(),
        min_salary_expected=15000,
    )
    assert sum(result.breakdown.values()) == result.total
