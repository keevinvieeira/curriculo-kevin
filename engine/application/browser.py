"""Thin Playwright session wrapper for real runs of the Application Prep Agent.

Deliberately minimal: everything that needs to be testable without a real browser
hitting a real ATS site (field extraction, answer resolution, the gate/state-machine
logic) lives in form_parser.py / answer_engine.py / session.py and takes a Playwright
Page as a plain argument. This module is just "how do we get a real Page open on a
real job posting" for an actual run — the one part that's inherently untestable in
CI/this sandbox without a live network call to the target ATS site.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Optional


@contextmanager
def open_browser(*, headless: bool = True) -> Iterator["Browser"]:  # noqa: F821 - Playwright type, imported lazily
    """Context manager yielding a launched Playwright Chromium Browser.

    Chromium ships pre-installed in the cloud dev sandbox (`/opt/pw-browsers`); on the
    user's own machine, `playwright install chromium` must be run once first — this
    function doesn't install anything itself, it only launches.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            yield browser
        finally:
            browser.close()


def open_job_posting_page(browser, url: str, *, timeout_ms: int = 30_000):
    """Open `url` in a fresh page/context of `browser` and wait for the DOM to settle.

    Returns the Playwright Page, left open and navigated — callers (session.py via a
    page_factory) are responsible for closing the context when done with it.
    """
    context = browser.new_context()
    page = context.new_page()
    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
    return page


def make_page_factory(url: str, *, headless: bool = True, timeout_ms: int = 30_000):
    """Build a zero-arg callable that launches a browser and returns a Page navigated
    to `url` — the shape `session.run_application_prep(..., page_factory=...)` needs
    for a real run. The browser/context are intentionally left open (not closed) so
    the caller can inspect the filled form visually before anything is submitted;
    call `.context.browser.close()` on the returned page when fully done with it.
    """
    from playwright.sync_api import sync_playwright

    def _factory():
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=headless)
        return open_job_posting_page(browser, url, timeout_ms=timeout_ms)

    return _factory
