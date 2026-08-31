"""Deduplication for the automation radar — no LLM involved, on purpose.

Checks, in order: normalized URL, ATS-specific posting id extracted from the URL,
exact normalized company+role, and finally token-overlap similarity on company+role
(same 0.6 threshold and technique `scripts/register_shortlist_applications.py`
already uses in `same_application()` — kept consistent rather than inventing a
different similarity method for the same kind of comparison).

Compares a freshly-discovered posting against both `data/jobs/*.json` (every vaga
ever adapted, regardless of automation status) and `applications.json` (things
already applied to, which might predate the job_store artifact format entirely).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "ref", "ref_id", "trk", "source", "fbclid", "gclid",
}
_STOPWORDS = {"at", "de", "do", "da", "em", "or", "e", "and", "the", "a", "o", "para", "in"}

TITLE_OVERLAP_THRESHOLD = 0.6  # igual ao usado em register_shortlist_applications.py


def normalize_url(url: str) -> str:
    """Lower-cases scheme/host, drops tracking query params and fragments/trailing slash."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query_pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS]
    query_pairs.sort()
    path = parts.path.rstrip("/") or "/"
    normalized = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query_pairs), ""))
    # Lower-cased wholesale: this is used for duplicate detection, not as a canonical
    # link to store/display, so incidental case differences in the path (common when
    # a URL is copy-pasted through a sharing tool) shouldn't cause a missed duplicate.
    return normalized.lower()


_ATS_ID_PATTERNS = [
    # Greenhouse: /jobs/1234567 ou ?gh_jid=1234567
    re.compile(r"greenhouse\.io/[^/]+/jobs/(\d+)", re.IGNORECASE),
    re.compile(r"[?&]gh_jid=(\d+)", re.IGNORECASE),
    # Lever: postings são UUIDs no final da URL
    re.compile(r"jobs\.lever\.co/[^/]+/([0-9a-f-]{36})", re.IGNORECASE),
    # Ashby: id UUID no final, ou /?jid=<uuid>
    re.compile(r"ashbyhq\.com/[^/]+/([0-9a-f-]{36})", re.IGNORECASE),
    re.compile(r"[?&]jid=([0-9a-f-]{36})", re.IGNORECASE),
]


def extract_ats_id(url: str) -> Optional[str]:
    """Best-effort extraction of a stable ATS posting id from a URL. None if not recognized."""
    if not url:
        return None
    for pattern in _ATS_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1).lower()
    return None


def normalize_tokens(value: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (value or "").casefold())) - _STOPWORDS


def token_overlap(a: str, b: str) -> float:
    """Jaccard similarity between the normalized token sets of two strings."""
    tokens_a, tokens_b = normalize_tokens(a), normalize_tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _existing_records(existing_jobs: Iterable[Dict[str, Any]], existing_applications: Iterable[Dict[str, Any]]):
    """Yield (record_id, url, company, role) for every known job artifact and application."""
    for job in existing_jobs:
        metadata = job.get("metadata", {})
        yield job.get("id"), metadata.get("url", ""), metadata.get("company_name", ""), metadata.get("role_title", "")
    for application in existing_applications:
        yield (
            application.get("source_job_id") or f"application:{application.get('id')}",
            application.get("url", ""),
            application.get("company", ""),
            application.get("role", ""),
        )


def find_duplicate(
    *,
    url: str,
    company: str,
    role: str,
    existing_jobs: List[Dict[str, Any]],
    existing_applications: List[Dict[str, Any]],
) -> Optional[str]:
    """Return the id of a matching existing job/application, or None if this looks new.

    Order of checks (cheapest/most-certain first): normalized URL, ATS id, exact
    normalized company+role, then token-overlap similarity as a fallback.
    """
    candidate_url_norm = normalize_url(url)
    candidate_ats_id = extract_ats_id(url)
    candidate_company_tokens = normalize_tokens(company)
    candidate_role_tokens = normalize_tokens(role)

    records = list(_existing_records(existing_jobs, existing_applications))

    if candidate_url_norm:
        for record_id, existing_url, _, _ in records:
            if existing_url and normalize_url(existing_url) == candidate_url_norm:
                return record_id

    if candidate_ats_id:
        for record_id, existing_url, _, _ in records:
            if existing_url and extract_ats_id(existing_url) == candidate_ats_id:
                return record_id

    for record_id, _, existing_company, existing_role in records:
        if normalize_tokens(existing_company) == candidate_company_tokens and normalize_tokens(existing_role) == candidate_role_tokens:
            return record_id

    for record_id, _, existing_company, existing_role in records:
        company_overlap = token_overlap(company, existing_company)
        role_overlap = token_overlap(role, existing_role)
        if company_overlap >= TITLE_OVERLAP_THRESHOLD and role_overlap >= TITLE_OVERLAP_THRESHOLD:
            return record_id

    return None
