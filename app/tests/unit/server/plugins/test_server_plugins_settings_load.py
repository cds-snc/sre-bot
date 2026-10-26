"""Behavior tests for the plugins settings slice on the [plugins.<area>] tables.

Each test writes a base file under tmp_path and installs it, so the slice reads
exactly the tables shown. A missing area table and an unknown area must fail
boot, and a quoted dotted entry-point name must stay one key. An environment
variable merges into an area key by key, which is how a developer switches one
plugin on from app/.env.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files
from server.configuration import load_configuration_files
from server.plugins.settings import PluginsSettings

pytestmark = pytest.mark.unit

_AREAS = """
[plugins.incident_response]
"incident.comms" = true

[plugins.cloud_operations]

[plugins.platform_access]
"access.sync" = false
"access.catalog" = false

[plugins.workplace_utilities]
rant = true
"""


@pytest.fixture(autouse=True)
def _no_plugins_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for area in ("INCIDENT_RESPONSE", "CLOUD_OPERATIONS", "PLATFORM_ACCESS", "WORKPLACE_UTILITIES"):
        monkeypatch.delenv(f"PLUGINS__{area}", raising=False)
    monkeypatch.setitem(PluginsSettings.model_config, "env_file", None)


def _install(tmp_path: Path, base: str) -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "ci.toml").write_text("", encoding="utf-8")
    install_configuration_files(load_configuration_files("ci", tmp_path))


def test_the_four_area_tables_load_with_dotted_names_as_single_keys(tmp_path: Path) -> None:
    _install(tmp_path, _AREAS)

    settings = PluginsSettings()

    assert settings.incident_response == {"incident.comms": True}
    assert settings.cloud_operations == {}
    assert settings.platform_access == {"access.sync": False, "access.catalog": False}
    assert settings.workplace_utilities == {"rant": True}


def test_a_missing_area_table_fails_naming_the_area(tmp_path: Path) -> None:
    _install(tmp_path, _AREAS.replace("[plugins.cloud_operations]\n", ""))

    with pytest.raises(ConfigurationError, match="cloud_operations"):
        PluginsSettings()


def test_an_unknown_area_table_fails_naming_it(tmp_path: Path) -> None:
    _install(tmp_path, _AREAS + '\n[plugins.billing]\n"billing.invoices" = true\n')

    with pytest.raises(ConfigurationError, match="billing"):
        PluginsSettings()


def test_an_environment_variable_switches_one_key_and_keeps_the_others(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path, _AREAS)
    monkeypatch.setenv("PLUGINS__PLATFORM_ACCESS", '{"access.sync": true}')

    settings = PluginsSettings()

    assert settings.platform_access == {"access.sync": True, "access.catalog": False}
