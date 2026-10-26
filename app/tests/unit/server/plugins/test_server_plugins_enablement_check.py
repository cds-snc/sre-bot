"""Behavior tests for the plugin enablement check over the [plugins.<area>] tables.

The slice is built from keyword arguments over a base file whose four area
tables are empty (dict values merge with the file's tables, so the checked-in
keys would otherwise join in), and the installed entry-point names are passed in
as a plain list, so no distribution metadata is read. Each failure must name the entry point (and the areas, for a
duplicate) so the person fixing base.toml knows which key to add, remove or move.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files
from server.configuration import load_configuration_files
from server.plugins.settings import PluginsSettings, check_plugin_enablement

pytestmark = pytest.mark.unit

_EMPTY_AREAS = (
    "[plugins.incident_response]\n[plugins.cloud_operations]\n[plugins.platform_access]\n[plugins.workplace_utilities]\n"
)


@pytest.fixture(autouse=True)
def _empty_area_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "base.toml").write_text(_EMPTY_AREAS, encoding="utf-8")
    (tmp_path / "ci.toml").write_text("", encoding="utf-8")
    install_configuration_files(load_configuration_files("ci", tmp_path))
    for area in ("INCIDENT_RESPONSE", "CLOUD_OPERATIONS", "PLATFORM_ACCESS", "WORKPLACE_UTILITIES"):
        monkeypatch.delenv(f"PLUGINS__{area}", raising=False)
    monkeypatch.setitem(PluginsSettings.model_config, "env_file", None)


def _settings(**areas: dict[str, bool]) -> PluginsSettings:
    return PluginsSettings(**areas)


def test_every_installed_entry_point_with_one_key_passes() -> None:
    settings = _settings(incident_response={"incident.comms": True}, platform_access={"access.sync": False})

    check_plugin_enablement(settings, ["access.sync", "incident.comms"])


def test_an_installed_entry_point_without_a_key_fails_naming_it() -> None:
    settings = _settings(incident_response={"incident.comms": True})

    with pytest.raises(ConfigurationError, match=r"'rant' has no enablement key"):
        check_plugin_enablement(settings, ["incident.comms", "rant"])


def test_a_key_naming_no_installed_entry_point_fails_naming_it() -> None:
    settings = _settings(incident_response={"incident.comms": True, "incident.comms_old": True})

    with pytest.raises(
        ConfigurationError, match=r"\[plugins.incident_response\] 'incident.comms_old' names no installed entry point"
    ):
        check_plugin_enablement(settings, ["incident.comms"])


def test_a_name_under_two_areas_fails_naming_the_name_and_both_areas() -> None:
    settings = _settings(incident_response={"rant": True}, workplace_utilities={"rant": True})

    with pytest.raises(ConfigurationError) as raised:
        check_plugin_enablement(settings, ["rant"])

    assert "'rant' is under [plugins.incident_response] and [plugins.workplace_utilities]" in str(raised.value)


def test_every_problem_is_reported_in_one_error() -> None:
    settings = _settings(incident_response={"ghost": True})

    with pytest.raises(ConfigurationError) as raised:
        check_plugin_enablement(settings, ["rant"])

    assert "'rant' has no enablement key" in str(raised.value)
    assert "'ghost' names no installed entry point" in str(raised.value)


def test_disabled_names_are_the_keys_set_to_false_in_any_area() -> None:
    settings = _settings(
        incident_response={"incident.comms": True},
        platform_access={"access.sync": False, "access.catalog": False},
        workplace_utilities={"rant": True},
    )

    assert settings.disabled() == frozenset({"access.sync", "access.catalog"})
