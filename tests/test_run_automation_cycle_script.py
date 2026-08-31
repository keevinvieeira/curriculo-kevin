"""Tests for scripts/run_automation_cycle.py's config-loading/source-building glue
(the part worth unit testing directly; the rest is just argparse + already-tested
engine.automation.workflow.run_automation_cycle)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_automation_cycle.py"


@pytest.fixture(scope="module")
def script_module():
    spec = importlib.util.spec_from_file_location("run_automation_cycle_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_sources_config_returns_empty_defaults_when_file_missing(script_module, tmp_path, monkeypatch):
    monkeypatch.setattr(script_module, "SOURCES_CONFIG_PATH", tmp_path / "does-not-exist.json")
    config = script_module._load_sources_config()
    assert config == {"greenhouse_boards": [], "lever_accounts": [], "ashby_boards": []}


def test_load_sources_config_reads_real_file(script_module, tmp_path, monkeypatch):
    config_path = tmp_path / "automation_sources.json"
    config_path.write_text(
        json.dumps({"greenhouse_boards": ["acme"], "lever_accounts": [], "ashby_boards": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(script_module, "SOURCES_CONFIG_PATH", config_path)
    config = script_module._load_sources_config()
    assert config["greenhouse_boards"] == ["acme"]


def test_build_sources_only_includes_configured_platforms(script_module):
    sources = script_module._build_sources(
        {"greenhouse_boards": ["acme"], "lever_accounts": [], "ashby_boards": []}
    )
    assert len(sources) == 1
    assert sources[0].name == "greenhouse"


def test_build_sources_returns_empty_list_for_empty_config(script_module):
    assert script_module._build_sources({"greenhouse_boards": [], "lever_accounts": [], "ashby_boards": []}) == []


def test_build_sources_includes_all_configured_platforms(script_module):
    sources = script_module._build_sources(
        {"greenhouse_boards": ["acme"], "lever_accounts": ["beta"], "ashby_boards": ["gamma"]}
    )
    assert {s.name for s in sources} == {"greenhouse", "lever", "ashby"}


def test_load_existing_applications_returns_empty_list_when_missing(script_module, tmp_path, monkeypatch):
    monkeypatch.setattr(script_module, "APPLICATIONS_PATH", tmp_path / "no-applications.json")
    assert script_module._load_existing_applications() == []
