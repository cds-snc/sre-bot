"""Boundary tests for the relocation of the pure Calendar-availability helpers."""

import tomllib
from pathlib import Path

import pytest
from packages.incident.scheduling import availability

from integrations.google_workspace import google_calendar, google_docs

APP_ROOT = Path(__file__).resolve().parents[5]
RELOCATED_NAMES = (
    "find_first_available_slot",
    "get_federal_holidays",
    "get_utc_hour",
    "identify_unavailable_users",
)


@pytest.mark.parametrize("name", RELOCATED_NAMES)
def test_relocated_helper_is_exposed_by_incident_scheduling(name):
    assert callable(getattr(availability, name))


@pytest.mark.parametrize("name", RELOCATED_NAMES)
def test_relocated_helper_removed_from_google_calendar(name):
    assert not hasattr(google_calendar, name)


@pytest.mark.parametrize("name", RELOCATED_NAMES)
def test_relocated_helper_absent_from_google_workspace_sources(name):
    package_dir = APP_ROOT / "integrations" / "google_workspace"
    offenders = [path.name for path in package_dir.glob("*.py") if name in path.read_text(encoding="utf-8")]
    assert offenders == []


def test_google_calendar_keeps_its_google_api_functions():
    assert callable(google_calendar.get_freebusy)
    assert callable(google_calendar.insert_event)


def test_extract_google_doc_id_stays_in_google_docs():
    """AC#2: extract_google_doc_id is out of scope and must not be relocated."""
    assert callable(google_docs.extract_google_doc_id)


def test_schedule_retro_uses_relocated_availability_helpers():
    from modules.incident import schedule_retro

    assert schedule_retro.find_first_available_slot is availability.find_first_available_slot
    assert schedule_retro.identify_unavailable_users is availability.identify_unavailable_users
    assert schedule_retro.get_freebusy is google_calendar.get_freebusy
    assert schedule_retro.insert_event is google_calendar.insert_event


def test_incident_scheduling_package_ships_no_hookimpls():
    """AC#6: the package is a plain importable module, not a registered plugin."""
    package_dir = APP_ROOT / "packages" / "incident" / "scheduling"
    offenders = [path.name for path in package_dir.rglob("*.py") if "hookimpl" in path.read_text(encoding="utf-8")]
    assert offenders == []


def test_incident_umbrella_is_namespace_only():
    """The umbrella registers nothing; only its subdomains do."""
    init = APP_ROOT / "packages" / "incident" / "__init__.py"
    assert init.read_text(encoding="utf-8").strip() == ""


def test_incident_scheduling_has_no_entry_point():
    """AC#6: no pyproject.toml entry-point line for the new package."""
    pyproject = tomllib.loads((APP_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    entry_points = pyproject.get("project", {}).get("entry-points", {})
    declared = {target for group in entry_points.values() for target in group.values()}
    assert not any(target == "packages.incident" or target.startswith("packages.incident.") for target in declared)
