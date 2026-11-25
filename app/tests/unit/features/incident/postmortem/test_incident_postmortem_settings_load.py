"""Unit tests for the [incident_postmortem] slice: the retro calendar id and the meeting search policy.

Settings are built from the checked-in configuration files the test run installs and
from the environment with monkeypatch; nothing is stubbed. Each id is declared empty in
base.toml, held by no environment file, read only from INCIDENT_POSTMORTEM__<FIELD>, and kept out of
the repr; an unknown key fails naming it. Every policy, tuning and bound value is declared in
base.toml with the slice's own default, and an out-of-range value fails the slice naming its field.
"""

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from typing import Any

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files, uninstall_configuration_files
from features.incident.postmortem.domain import HolidayLookupFailure
from features.incident.postmortem.settings import IncidentPostmortemSettings, get_incident_postmortem_settings
from server.configuration.loader import CONFIG_DIR

pytestmark = pytest.mark.unit

_FIELDS = ("calendar_id",)


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setitem(IncidentPostmortemSettings.model_config, "env_file", None)
    get_incident_postmortem_settings.cache_clear()
    yield
    get_incident_postmortem_settings.cache_clear()


_POLICY = {
    "time_zone": "America/Toronto",
    "window_start": "13:00",
    "window_end": "15:00",
    "weekdays": [1, 2, 3, 4, 5],
    "duration_minutes": 30,
    "slot_step_minutes": 30,
    "search_days": 60,
    "default_start_offset_days": 1,
    "max_start_offset_days": 60,
    "optional_quorum_percent": 50,
    "holiday_lookup_failure": "proceed",
}


def _base() -> dict[str, Any]:
    return tomllib.loads((CONFIG_DIR / "base.toml").read_text(encoding="utf-8"))["incident_postmortem"]


def test_base_declares_every_id_empty_and_the_search_policy() -> None:
    assert _base() == {**dict.fromkeys(_FIELDS, ""), **_POLICY}


def test_the_slice_defaults_mirror_base() -> None:
    """A slice built without the files' policy keys answers what base.toml declares."""
    defaults = {name: info.default for name, info in IncidentPostmortemSettings.model_fields.items() if name in _POLICY}

    assert defaults == {
        "time_zone": "America/Toronto",
        "window_start": time(13, 0),
        "window_end": time(15, 0),
        "weekdays": (1, 2, 3, 4, 5),
        "duration_minutes": 30,
        "slot_step_minutes": 30,
        "search_days": 60,
        "default_start_offset_days": 1,
        "max_start_offset_days": 60,
        "optional_quorum_percent": 50,
        "holiday_lookup_failure": HolidayLookupFailure.PROCEED,
    }


def test_the_installed_files_load_the_policy() -> None:
    settings = IncidentPostmortemSettings()

    assert settings.window_start == time(13, 0)
    assert settings.weekdays == (1, 2, 3, 4, 5)
    assert settings.holiday_lookup_failure is HolidayLookupFailure.PROCEED


@pytest.mark.parametrize("environment", ["ci", "local", "production"])
def test_no_environment_file_holds_an_id(environment: str) -> None:
    values = tomllib.loads((CONFIG_DIR / f"{environment}.toml").read_text(encoding="utf-8"))

    assert not set(values.get("incident_postmortem", {})) & set(_FIELDS)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("time_zone", '"Mars/Olympus"'),
        ("window_end", '"13:00"'),
        ("weekdays", "[]"),
        ("weekdays", "[1, 8]"),
        ("weekdays", "[1, 1]"),
        ("duration_minutes", "121"),
        ("duration_minutes", "0"),
        ("slot_step_minutes", "0"),
        ("search_days", "0"),
        ("search_days", "121"),
        ("default_start_offset_days", "61"),
        ("max_start_offset_days", "0"),
        ("optional_quorum_percent", "101"),
        ("optional_quorum_percent", "-1"),
        ("holiday_lookup_failure", '"ignore"'),
    ],
)
def test_an_out_of_range_policy_value_fails_naming_its_field(tmp_path: Path, key: str, value: str) -> None:
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text(f"[incident_postmortem]\n{key} = {value}\n")
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match=key):
        IncidentPostmortemSettings()


@pytest.mark.parametrize("field", _FIELDS)
def test_an_id_is_empty_by_default_and_read_from_the_environment(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    """An empty id does not fail the slice; the legacy reader fails at first use instead."""
    assert getattr(IncidentPostmortemSettings(), field) == ""

    monkeypatch.setenv(f"INCIDENT_POSTMORTEM__{field.upper()}", "id-from-env")

    assert getattr(IncidentPostmortemSettings(), field) == "id-from-env"


def test_an_id_never_appears_in_the_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    for field in _FIELDS:
        monkeypatch.setenv(f"INCIDENT_POSTMORTEM__{field.upper()}", f"value-of-{field}")

    rendered = repr(IncidentPostmortemSettings())

    assert not [field for field in _FIELDS if f"value-of-{field}" in rendered]


def test_an_unknown_key_in_the_table_fails_naming_it(tmp_path: Path) -> None:
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text('[incident_postmortem]\nunknown_id = "x"\n')
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(ConfigurationError, match="unknown_id"):
        IncidentPostmortemSettings()


def test_building_before_install_raises() -> None:
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError):
        IncidentPostmortemSettings()


def test_the_provider_returns_one_cached_instance() -> None:
    assert get_incident_postmortem_settings() is get_incident_postmortem_settings()
