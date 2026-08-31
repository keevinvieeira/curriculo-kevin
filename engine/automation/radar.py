"""Job discovery sources for the automation radar (v1 scope).

Per the user's explicit decision: v1 sources are public ATS job-board endpoints
(Greenhouse, Lever, Ashby — the same three ATS the Application Prep Agent supports,
so a discovered posting is also one we can eventually fill out) plus institutional
career pages and general public web search. LinkedIn and Gupy are deliberately left
out of the automation (scraping both violates their ToS and risks the user's personal
account) — those stay manual, exactly as today.

What's fully implemented and unit-tested here: GreenhouseSource and LeverSource,
against their documented public JSON APIs (no auth, no scraping — these are the
official machine-readable job-board feeds these ATS provide). AshbySource is
implemented defensively (multiple fallback field names) because this module's author
could not get a live, approved fetch of Ashby's current API docs during this session —
verify field names against https://developers.ashbyhq.com before relying on it in
production, and adjust `_ASHBY_TITLE_KEYS` etc. if they've changed.

Institutional career pages and general public web search are intentionally left as a
`JobSource` extension point (see `CustomSource` at the bottom) rather than implemented
per-site here: career page HTML is different for every company and scraping it
reliably needs per-site rules, which belongs in a follow-up once specific target
companies are known. `discover_all()` isolates failures per source, so a broken or
rate-limited source never blocks the whole radar cycle.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import requests

REQUEST_TIMEOUT_SECONDS = 15


@dataclass
class RawJobPosting:
    """A normalized posting, before scoring/dedupe/adaptation happen."""

    company: str
    title: str
    url: str
    description: str = ""
    location: str = ""
    remote: Optional[bool] = None
    employment_type: str = ""
    salary_range: Optional[str] = None
    posted_at: Optional[str] = None
    source: str = ""
    source_id: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class JobSource(ABC):
    """Common interface every discovery source implements."""

    name: str = "unknown"

    @abstractmethod
    def discover(self) -> List[RawJobPosting]:
        """Return every currently-listed posting from this source. Never raises on a
        single bad record — skip it and keep going; `discover_all()` handles a whole
        source failing (e.g. the API being down)."""


class GreenhouseSource(JobSource):
    """Public Greenhouse Job Board API — https://developers.greenhouse.io/job-board.html

    No API key. One HTTP call per company "board token" (the slug in
    boards.greenhouse.io/<token>). Confirmed fields (2026-08-31): id, title,
    updated_at, location, absolute_url, content, departments. Greenhouse does not
    natively expose salary, employment_type, or a remote flag — those stay unset here
    unless present in `content` (left for a future improvement, not guessed at).
    """

    name = "greenhouse"

    def __init__(self, board_tokens: List[str], session: Optional[requests.Session] = None):
        self.board_tokens = board_tokens
        self.session = session or requests.Session()

    def discover(self) -> List[RawJobPosting]:
        postings: List[RawJobPosting] = []
        for token in self.board_tokens:
            url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
            for job in payload.get("jobs", []):
                location = job.get("location")
                location_str = location.get("name", "") if isinstance(location, dict) else (location or "")
                postings.append(
                    RawJobPosting(
                        company=token,
                        title=job.get("title", ""),
                        url=job.get("absolute_url", ""),
                        description=job.get("content", "") or "",
                        location=location_str,
                        posted_at=job.get("updated_at"),
                        source=self.name,
                        source_id=str(job.get("id")) if job.get("id") is not None else None,
                        raw=job,
                    )
                )
        return postings


class LeverSource(JobSource):
    """Public Lever Postings API — https://api.lever.co/v0/postings/{account}?mode=json

    Confirmed fields (2026-08-31): id, text, categories.{location,team,commitment,department},
    hostedUrl, applyUrl, createdAt (ms epoch), workplaceType.
    """

    name = "lever"

    def __init__(self, accounts: List[str], session: Optional[requests.Session] = None):
        self.accounts = accounts
        self.session = session or requests.Session()

    def discover(self) -> List[RawJobPosting]:
        postings: List[RawJobPosting] = []
        for account in self.accounts:
            url = f"https://api.lever.co/v0/postings/{account}?mode=json"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            for job in response.json():
                categories = job.get("categories", {}) or {}
                created_at_ms = job.get("createdAt")
                posted_at = None
                if isinstance(created_at_ms, (int, float)):
                    from datetime import datetime, timezone

                    posted_at = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc).isoformat()
                workplace_type = (job.get("workplaceType") or "").lower()
                postings.append(
                    RawJobPosting(
                        company=account,
                        title=job.get("text", ""),
                        url=job.get("hostedUrl", "") or job.get("applyUrl", ""),
                        description=job.get("descriptionPlain", "") or job.get("description", "") or "",
                        location=categories.get("location", ""),
                        remote=workplace_type in {"remote", "hybrid"} or None,
                        employment_type=categories.get("commitment", ""),
                        posted_at=posted_at,
                        source=self.name,
                        source_id=job.get("id"),
                        raw=job,
                    )
                )
        return postings


class AshbySource(JobSource):
    """Public Ashby Job Board API — https://api.ashbyhq.com/posting-api/job-board/{boardName}

    NOTE: field names below were not verified live against Ashby's current docs during
    this session (fetch was blocked pending an approval that didn't arrive in time) —
    this implementation tries several plausible key names defensively and should be
    re-checked against https://developers.ashbyhq.com before depending on it for real
    discovery. Prefer Greenhouse/Lever until this has been validated against a live
    response.
    """

    name = "ashby"
    _TITLE_KEYS = ("title",)
    _URL_KEYS = ("jobUrl", "applyUrl", "url")
    _LOCATION_KEYS = ("location", "locationName")
    _POSTED_KEYS = ("publishedAt", "publishedDate", "createdAt")
    _DESCRIPTION_KEYS = ("descriptionPlain", "descriptionHtml", "description")

    def __init__(self, board_names: List[str], session: Optional[requests.Session] = None):
        self.board_names = board_names
        self.session = session or requests.Session()

    @staticmethod
    def _first(job: Dict[str, Any], keys: tuple) -> Optional[Any]:
        for key in keys:
            if job.get(key):
                return job[key]
        return None

    def discover(self) -> List[RawJobPosting]:
        postings: List[RawJobPosting] = []
        for board in self.board_names:
            url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
            response = self.session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
            for job in payload.get("jobs", []):
                postings.append(
                    RawJobPosting(
                        company=board,
                        title=self._first(job, self._TITLE_KEYS) or "",
                        url=self._first(job, self._URL_KEYS) or "",
                        description=self._first(job, self._DESCRIPTION_KEYS) or "",
                        location=self._first(job, self._LOCATION_KEYS) or "",
                        remote=bool(job.get("isRemote")) if "isRemote" in job else None,
                        employment_type=job.get("employmentType", ""),
                        posted_at=self._first(job, self._POSTED_KEYS),
                        source=self.name,
                        source_id=str(job.get("id")) if job.get("id") is not None else None,
                        raw=job,
                    )
                )
        return postings


class CustomSource(JobSource):
    """Extension point for institutional career pages / public web search.

    Not implemented per-site here on purpose — every career page needs its own
    parsing rules, and building those blind (without a concrete target list of
    companies to watch) would just be guessed-at code nobody could verify. Wrap
    whatever fetch+parse logic a specific site needs in a `Callable[[], List[RawJobPosting]]`
    and register it here; `discover_all()` treats it like any other source.
    """

    def __init__(self, name: str, fetch_fn: Callable[[], List[RawJobPosting]]):
        self.name = name
        self._fetch_fn = fetch_fn

    def discover(self) -> List[RawJobPosting]:
        return self._fetch_fn()


@dataclass
class SourceError:
    source_name: str
    error: str


def discover_all(sources: List[JobSource]) -> tuple[List[RawJobPosting], List[SourceError]]:
    """Run every source, isolating failures so one broken/rate-limited source never
    blocks the rest of the radar cycle. Returns (postings, errors)."""
    postings: List[RawJobPosting] = []
    errors: List[SourceError] = []
    for source in sources:
        try:
            postings.extend(source.discover())
        except Exception as exc:  # noqa: BLE001 - deliberately broad, isolate per source
            errors.append(SourceError(source_name=source.name, error=str(exc)))
    return postings, errors
