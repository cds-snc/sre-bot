"""Unit tests for the incident core settings slice.

Settings are built from the environment with monkeypatch; nothing is stubbed.
The table names default to the provisioned tables, the new-incident policy is
unset by default, and both reject values that could never work.
"""

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings, get_incident_core_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    get_incident_core_settings.cache_clear()
    yield
    get_incident_core_settings.cache_clear()


def test_table_names_default_to_the_provisioned_tables() -> None:
    """Defaults match the tables terraform/dynamodb.tf creates, so no environment needs to set them."""
    settings = IncidentCoreSettings()

    assert settings.INCIDENTS_TABLE == "incidents"
    assert settings.TIMELINE_TABLE == "sre_bot_incident_timeline"


def test_table_names_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each table name has its own INCIDENT_CORE__ key."""
    monkeypatch.setenv("INCIDENT_CORE__INCIDENTS_TABLE", "incidents_test")
    monkeypatch.setenv("INCIDENT_CORE__TIMELINE_TABLE", "timeline_test")

    settings = IncidentCoreSettings()

    assert settings.INCIDENTS_TABLE == "incidents_test"
    assert settings.TIMELINE_TABLE == "timeline_test"


@pytest.mark.parametrize("key", ["INCIDENT_CORE__INCIDENTS_TABLE", "INCIDENT_CORE__TIMELINE_TABLE"])
def test_a_blank_table_name_is_rejected_naming_the_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    """A blank name could never address a table, so the slice fails validation."""
    monkeypatch.setenv(key, "  ")

    with pytest.raises(ValidationError, match=key):
        IncidentCoreSettings()


def test_the_new_incident_policy_is_unset_by_default() -> None:
    """Unset resolves later to the only configured system, so most instances never set it."""
    assert IncidentCoreSettings().NEW_INCIDENT_SYSTEM is None


@pytest.mark.parametrize(("value", "expected"), [("slack", WorkplaceSystem.SLACK), ("google", WorkplaceSystem.GOOGLE)])
def test_the_new_incident_policy_names_a_system(monkeypatch: pytest.MonkeyPatch, value: str, expected: WorkplaceSystem) -> None:
    """The policy holds a system, never a tenant id."""
    monkeypatch.setenv("INCIDENT_CORE__NEW_INCIDENT_SYSTEM", value)

    assert IncidentCoreSettings().NEW_INCIDENT_SYSTEM is expected


def test_an_unknown_system_in_the_policy_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The system is a closed enum, validated strictly where it is chosen."""
    monkeypatch.setenv("INCIDENT_CORE__NEW_INCIDENT_SYSTEM", "T0123ABC")

    with pytest.raises(ValidationError, match="INCIDENT_CORE__NEW_INCIDENT_SYSTEM"):
        IncidentCoreSettings()


def test_the_provider_returns_one_cached_instance() -> None:
    """Every caller shares the process-wide slice."""
    assert get_incident_core_settings() is get_incident_core_settings()
