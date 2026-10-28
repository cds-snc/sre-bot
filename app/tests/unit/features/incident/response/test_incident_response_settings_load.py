"""Unit tests for the [incident_response] slice: the declare path's Slack ids and the handbook id.

Settings are built from the checked-in configuration files the test run installs (or the
real loader for one environment) and from the environment with monkeypatch; nothing is
stubbed. The Slack ids are deployment configuration: declared empty in base.toml, set in
production.toml only. The handbook id is non-public: declared empty in base.toml, held by no
environment file, read only from INCIDENT_RESPONSE__HANDBOOK_ID, and kept out of the repr. The
legacy [incident] table and its INCIDENT__* names reach no field; an unknown key fails naming it.
"""

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files, uninstall_configuration_files
from features.incident.response.settings import IncidentResponseSettings, get_incident_response_settings
from server.configuration.loader import CONFIG_DIR, load_configuration_files

pytestmark = pytest.mark.unit

_FIELDS = ("handbook_id",)
_SLACK_IDS = ("announcement_channel_id", "security_group_id", "notify_management_group_id")
_RETIRED_NAMES = (
    "INCIDENT__INCIDENT_CHANNEL",
    "INCIDENT__SLACK_SECURITY_USER_GROUP_ID",
    "INCIDENT__SLACK_NOTIFY_MGMT_USER_GROUP_ID",
    "INCIDENT_CHANNEL",
    "SLACK_SECURITY_USER_GROUP_ID",
    "SLACK_NOTIFY_MGMT_USER_GROUP_ID",
)


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(IncidentResponseSettings.model_config, "env_file", None)
    for name in (*_RETIRED_NAMES, *(f"INCIDENT_RESPONSE__{field.upper()}" for field in _SLACK_IDS)):
        monkeypatch.delenv(name, raising=False)
    get_incident_response_settings.cache_clear()
    yield
    get_incident_response_settings.cache_clear()


def test_base_declares_every_key_empty() -> None:
    base = tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))

    assert base["incident_response"] == dict.fromkeys((*_SLACK_IDS, *_FIELDS), "")
    assert "incident" not in base


@pytest.mark.parametrize("environment", ["ci", "local", "production"])
def test_no_environment_file_holds_a_non_public_id(environment: str) -> None:
    values = tomllib.loads((CONFIG_DIR / f"{environment}.toml").read_text(encoding="utf-8"))

    assert not set(values.get("incident_response", {})) & set(_FIELDS)
    assert "incident" not in values


def test_production_resolves_the_slack_ids_production_ran_on() -> None:
    """The values are the blob lines' (deploy check 'features', TASK-111.14), moved unchanged."""
    install_configuration_files(load_configuration_files("production"))

    settings = IncidentResponseSettings()

    assert (settings.announcement_channel_id, settings.security_group_id, settings.notify_management_group_id) == (
        "CUYR73ESX",
        "S057X3XB5FX",
        "S0BC6L00PUG",
    )


@pytest.mark.parametrize("environment", ["local", "ci"])
def test_local_and_ci_configure_no_slack_id(environment: str) -> None:
    """Local shares the production workspace, so no production id is a default where developers run the bot."""
    install_configuration_files(load_configuration_files(environment))

    settings = IncidentResponseSettings()

    assert [getattr(settings, field) for field in _SLACK_IDS] == ["", "", ""]


def test_a_prefixed_environment_variable_beats_the_files(monkeypatch: pytest.MonkeyPatch) -> None:
    install_configuration_files(load_configuration_files("production"))
    monkeypatch.setenv("INCIDENT_RESPONSE__ANNOUNCEMENT_CHANNEL_ID", "C0OVERRIDE")

    assert IncidentResponseSettings().announcement_channel_id == "C0OVERRIDE"


@pytest.mark.parametrize("name", _RETIRED_NAMES)
def test_the_legacy_names_reach_no_field(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "C0LEGACY")

    settings = IncidentResponseSettings()

    assert "C0LEGACY" not in [getattr(settings, field) for field in _SLACK_IDS]


def test_the_legacy_table_fails_the_slice_naming_it(tmp_path: Path) -> None:
    """A file still holding an [incident] key under [incident_response] is an unknown key, not a silent drop."""
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text('[incident_response]\nincident_channel = "C0OLD"\n')
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match="incident_channel"):
        IncidentResponseSettings()


@pytest.mark.parametrize("field", _FIELDS)
def test_an_id_is_empty_by_default_and_read_from_the_environment(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    """An empty id does not fail the slice; the legacy reader fails at first use instead."""
    assert getattr(IncidentResponseSettings(), field) == ""

    monkeypatch.setenv(f"INCIDENT_RESPONSE__{field.upper()}", "id-from-env")

    assert getattr(IncidentResponseSettings(), field) == "id-from-env"


def test_an_id_never_appears_in_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in _FIELDS:
        monkeypatch.setenv(f"INCIDENT_RESPONSE__{field.upper()}", f"value-of-{field}")

    rendered = repr(IncidentResponseSettings())

    assert not [field for field in _FIELDS if f"value-of-{field}" in rendered]


def test_an_unknown_key_in_the_table_fails_naming_it(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text('[incident_response]\nunknown_id = "x"\n')
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match="unknown_id"):
        IncidentResponseSettings()


def test_building_before_install_raises() -> None:
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError):
        IncidentResponseSettings()


def test_the_provider_returns_one_cached_instance() -> None:
    assert get_incident_response_settings() is get_incident_response_settings()
