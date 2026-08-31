"""Shared pytest fixtures/setup for the Career OS automation test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def _playwright_browser():
    """One headless Chromium instance shared across the whole test session — the
    Application Prep Agent tests (Fase 5) drive real Playwright against local HTML
    fixtures (page.set_content), never a real network request, so this is fast and
    fully offline."""
    pytest.importorskip("playwright")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def playwright_page(_playwright_browser):
    """A fresh Playwright Page (own browser context) per test, closed afterwards."""
    context = _playwright_browser.new_context()
    page = context.new_page()
    yield page
    context.close()
