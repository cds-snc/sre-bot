"""Unit tests for the incident core settings slice, the [incident_core] table.

Settings are built from the checked-in configuration files the test run installs and
from the environment with monkeypatch; nothing is stubbed. The table names default to
the provisioned tables, the new-incident policy is unset by default, both reject values
that could never work, and the Google document ids are non-public values: declared empty
in base.toml, held by no configuration file, set only from the environment.
"""

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files, uninstall_configuration_files
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import IncidentCoreSettings, get_incident_core_settings
from server.configuration.loader import CONFIG_DIR

pytestmark = pytest.mark.unit

_DOCUMENT_IDS = ("folder_id", "report_template_id", "list_sheet_id")


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(IncidentCoreSettings.model_config, "env_file", None)
    get_incident_core_settings.cache_clear()
    yield
    get_incident_core_settings.cache_clear()


def test_table_names_default_to_the_provisioned_tables() -> None:
    """Defaults match the tables terraform/dynamodb.tf creates, so no environment needs to set them."""
    settings = IncidentCoreSettings()

    assert settings.incidents_table == "incidents"
    assert settings.timeline_table == "sre_bot_incident_timeline"


def test_table_names_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each table name keeps its INCIDENT_CORE__ name."""
    monkeypatch.setenv("INCIDENT_CORE__INCIDENTS_TABLE", "incidents_test")
    monkeypatch.setenv("INCIDENT_CORE__TIMELINE_TABLE", "timeline_test")

    settings = IncidentCoreSettings()

    assert settings.incidents_table == "incidents_test"
    assert settings.timeline_table == "timeline_test"


@pytest.mark.parametrize("key", ["incidents_table", "timeline_table"])
def test_a_blank_table_name_is_rejected_naming_the_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    """A blank name could never address a table, so the slice fails naming the key."""
    monkeypatch.setenv(f"INCIDENT_CORE__{key.upper()}", "  ")

    with pytest.raises(ConfigurationError, match=key):
        IncidentCoreSettings()


def test_the_new_incident_policy_is_unset_by_default() -> None:
    """Unset resolves later to the only configured system, so most instances never set it."""
    assert IncidentCoreSettings().new_incident_system is None


@pytest.mark.parametrize(("value", "expected"), [("slack", WorkplaceSystem.SLACK), ("google", WorkplaceSystem.GOOGLE)])
def test_the_new_incident_policy_names_a_system(monkeypatch: pytest.MonkeyPatch, value: str, expected: WorkplaceSystem) -> None:
    """The policy holds a system, never a tenant id."""
    monkeypatch.setenv("INCIDENT_CORE__NEW_INCIDENT_SYSTEM", value)

    assert IncidentCoreSettings().new_incident_system is expected


def test_an_unknown_system_in_the_policy_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The system is a closed enum, validated strictly where it is chosen."""
    monkeypatch.setenv("INCIDENT_CORE__NEW_INCIDENT_SYSTEM", "T0123ABC")

    with pytest.raises(ConfigurationError, match="INCIDENT_CORE__NEW_INCIDENT_SYSTEM"):
        IncidentCoreSettings()


def test_base_declares_the_tables_and_empty_document_ids() -> None:
    """Every default lives in base.toml; the ids are declared empty there."""
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert base["incident_core"] == {
        "incidents_table": "incidents",
        "timeline_table": "sre_bot_incident_timeline",
        "folder_id": "",
        "report_template_id": "",
        "list_sheet_id": "",
    }


@pytest.mark.parametrize("environment", ["ci", "local", "production"])
def test_no_environment_file_holds_the_table_or_a_document_id(environment: str) -> None:
    """Production sets no INCIDENT_CORE__ value and no file names an id: the defaults are the provisioned tables."""
    values = tomllib.loads((CONFIG_DIR / f"{environment}.toml").read_text(encoding="utf-8"))

    assert "incident_core" not in values


@pytest.mark.parametrize("field", _DOCUMENT_IDS)
def test_a_document_id_is_empty_by_default_and_read_from_the_environment(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    """An empty id does not fail the slice; the environment supplies the value."""
    assert getattr(IncidentCoreSettings(), field) == ""

    monkeypatch.setenv(f"INCIDENT_CORE__{field.upper()}", "id-from-env")

    assert getattr(IncidentCoreSettings(), field) == "id-from-env"


def test_a_document_id_never_appears_in_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-public value is never logged in full, so the slice's repr leaves it out."""
    monkeypatch.setenv("INCIDENT_CORE__FOLDER_ID", "folder-secretish")

    assert "folder-secretish" not in repr(IncidentCoreSettings())


def test_an_unknown_key_in_the_table_fails_naming_it(tmp_path: Path) -> None:
    """extra=forbid: a mistyped key fails instead of being ignored."""
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text('[incident_core]\nincidents_tabel = "x"\n')
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match="incidents_tabel"):
        IncidentCoreSettings()


def test_building_before_install_raises() -> None:
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError):
        IncidentCoreSettings()


def test_the_provider_returns_one_cached_instance() -> None:
    """Every caller shares the process-wide slice."""
    assert get_incident_core_settings() is get_incident_core_settings()
