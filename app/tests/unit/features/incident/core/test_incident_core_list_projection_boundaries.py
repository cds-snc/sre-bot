"""The incident list projection's public shape and import boundaries.

The Protocol offers exactly ``append_row`` and ``update_status``, both
coroutines; the Google Sheets adapter reaches the sheet through
``integrations.google_workspace`` and nothing under ``features/incident``
imports ``infrastructure.spreadsheets``; the provider is cached.
"""

import ast
import inspect
from pathlib import Path

import pytest

from features.incident.core import api
from features.incident.core.adapters import google_sheets
from features.incident.core.adapters.google_sheets import GoogleSheetsIncidentListProjection

pytestmark = pytest.mark.unit

INCIDENT_ROOT = Path(api.__file__).resolve().parents[1]


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_protocol_has_exactly_append_row_and_update_status() -> None:
    """The port is write-only: no read, delete or list method."""
    members = {name for name, _ in inspect.getmembers(api.IncidentListProjection, inspect.isfunction) if not name.startswith("_")}

    assert members == {"append_row", "update_status"}
    assert inspect.iscoroutinefunction(api.IncidentListProjection.append_row)
    assert inspect.iscoroutinefunction(api.IncidentListProjection.update_status)


def test_adapter_methods_are_coroutines() -> None:
    """The adapter offloads inside itself; callers await."""
    assert inspect.iscoroutinefunction(GoogleSheetsIncidentListProjection.append_row)
    assert inspect.iscoroutinefunction(GoogleSheetsIncidentListProjection.update_status)


def test_adapter_uses_the_google_workspace_gateway() -> None:
    """The adapter imports the gateway client, not the shared spreadsheet provider."""
    modules = _imported_modules(Path(google_sheets.__file__))

    assert "integrations.google_workspace.client" in modules


def test_nothing_in_the_incident_feature_imports_the_spreadsheet_infrastructure() -> None:
    """The incident umbrella never reaches infrastructure.spreadsheets."""
    offenders = [
        str(path.relative_to(INCIDENT_ROOT))
        for path in INCIDENT_ROOT.rglob("*.py")
        if any(module.startswith("infrastructure.spreadsheets") for module in _imported_modules(path))
    ]

    assert offenders == []


def test_provider_is_cached_and_returns_the_sheets_adapter() -> None:
    """One process-wide projection, on Google Sheets."""
    api.get_incident_list_projection.cache_clear()
    try:
        first = api.get_incident_list_projection()
        assert api.get_incident_list_projection() is first
        assert isinstance(first, GoogleSheetsIncidentListProjection)
    finally:
        api.get_incident_list_projection.cache_clear()
