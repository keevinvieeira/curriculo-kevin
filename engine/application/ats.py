"""ATS platform detection for the Application Prep Agent.

v1 scope is intentionally the same three ATS the radar (engine/automation/radar.py)
already discovers postings from: Greenhouse, Lever, Ashby. Detecting the platform
from the URL is enough to pick which form-filling conventions to expect; the actual
field extraction in form_parser.py is mostly platform-agnostic (it reads labels/names
generically), so a wrong or unknown detection only affects a couple of platform-
specific selectors, never crashes the whole run.
"""
from __future__ import annotations

import re
from typing import Optional

_PATTERNS = [
    ("greenhouse", re.compile(r"greenhouse\.io|[?&]gh_jid=", re.IGNORECASE)),
    ("lever", re.compile(r"jobs\.lever\.co", re.IGNORECASE)),
    ("ashby", re.compile(r"ashbyhq\.com|[?&]jid=", re.IGNORECASE)),
]

SUPPORTED_ATS = ("greenhouse", "lever", "ashby")


def detect_ats_platform(url: str) -> Optional[str]:
    """Return "greenhouse" / "lever" / "ashby", or None if the URL doesn't match any
    ATS this agent knows how to fill. None means the caller must not attempt to run
    the Application Prep Agent on this posting (v1 supports only these three)."""
    if not url:
        return None
    for name, pattern in _PATTERNS:
        if pattern.search(url):
            return name
    return None


def is_supported(url: str) -> bool:
    return detect_ats_platform(url) is not None
