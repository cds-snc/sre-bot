"""Unit tests for loading the MaxMind vendor slice from the [maxmind] table.

Each test installs a base and a local file from tmp_path (``install_maxmind_files``) with every
MaxMind variable removed and the .env file disabled (the autouse isolation fixture), so it
observes only the values it writes and sets. MaxMind has no credential and no tenant id: the
entry is the database file the deployment chooses, [maxmind.tenant] database_path. Boot checks
its shape only; the file's presence is the healthcheck's. The retired MAXMIND_* names are ignored.
"""

from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice
from integrations.maxmind.settings import MaxMindSettings, get_maxmind_settings
from tests.unit.integrations.maxmind.conftest import DATABASE_PATH, RETIRED_NAMES, TENANT, install_maxmind_files

pytestmark = pytest.mark.unit


def test_maxmind_settings_is_a_slice_on_the_maxmind_table() -> None:
    config = MaxMindSettings.model_config

    assert issubclass(MaxMindSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("maxmind",)
    assert config.get("env_prefix") == "MAXMIND__"
    assert config.get("extra") == "forbid"


def test_nothing_set_is_maxmind_not_configured(tmp_path: Path) -> None:
    install_maxmind_files(tmp_path)

    assert MaxMindSettings().tenant is None


def test_the_tenant_entry_names_the_database_file(tmp_path: Path) -> None:
    install_maxmind_files(tmp_path, environment=TENANT)

    settings = MaxMindSettings()

    assert settings.tenant is not None
    assert settings.tenant.database_path == DATABASE_PATH


def test_a_missing_database_file_still_boots(tmp_path: Path) -> None:
    """No I/O at boot: the file's presence is the healthcheck's."""
    install_maxmind_files(tmp_path, environment='[maxmind.tenant]\ndatabase_path = "/does/not/exist.mmdb"\n')

    assert MaxMindSettings().tenant is not None


@pytest.mark.parametrize(
    ("files", "key"),
    [
        ('[maxmind.tenant]\ndatabase_path = ""\n', "database_path"),
        ("[maxmind.tenant]\n", "database_path"),
        (TENANT + 'license_key = "x"\n', "license_key"),
        ('[maxmind]\ndb_path = "x"\n', "db_path"),
    ],
)
def test_a_malformed_entry_or_unknown_key_fails_naming_it(tmp_path: Path, files: str, key: str) -> None:
    install_maxmind_files(tmp_path, environment=files)

    with pytest.raises(ConfigurationError, match=key):
        MaxMindSettings()


def test_the_retired_names_are_ignored_in_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install_maxmind_files(tmp_path)
    for name in RETIRED_NAMES:
        monkeypatch.setenv(name, "/retired.mmdb")

    assert MaxMindSettings().tenant is None


def test_get_maxmind_settings_is_cached(tmp_path: Path) -> None:
    install_maxmind_files(tmp_path)

    assert get_maxmind_settings() is get_maxmind_settings()
