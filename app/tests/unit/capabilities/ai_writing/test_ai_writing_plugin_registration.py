"""Tests for the AI writing capability's plugin registration.

The installed distribution metadata is read, which is what boot does when it loads plugins, and
the project file is parsed for the import-linter contract and the base configuration for the
enablement key, so a stale target fails here rather than at startup or in CI.
"""

import tomllib
from importlib.metadata import entry_points
from pathlib import Path

import pytest

import capabilities.ai_writing.plugin as plugin_module
from contracts.plugins.namespace import PLUGIN_NAMESPACE

pytestmark = pytest.mark.unit

APP = Path(__file__).resolve().parents[4]


def test_the_entry_point_names_the_plugin_module() -> None:
    (entry_point,) = [ep for ep in entry_points(group=PLUGIN_NAMESPACE) if ep.name == "ai_writing"]

    assert entry_point.value == "capabilities.ai_writing.plugin"
    assert entry_point.load() is plugin_module


def test_the_plugin_module_is_protected_and_the_api_is_not() -> None:
    """Features import api.py, so only the plugin module is closed to them (contract (m))."""
    contracts = tomllib.loads((APP / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["importlinter"]["contracts"]
    protected = {module for contract in contracts for module in contract.get("protected_modules", ())}

    assert "capabilities.ai_writing.plugin" in protected
    assert "capabilities.ai_writing" not in protected


def test_the_enablement_key_is_on_in_the_incident_response_area() -> None:
    base = tomllib.loads((APP / "config" / "base.toml").read_text(encoding="utf-8"))

    assert base["plugins"]["incident_response"]["ai_writing"] is True


def test_it_declares_no_requirement() -> None:
    """AI writing is optional backing: it reports availability instead of failing boot."""
    assert plugin_module.register_requirements() == []
