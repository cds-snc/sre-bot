"""Unit tests for loading the directory slice from the [directory] table.

Each test installs a base and a local file from tmp_path with every DIRECTORY variable removed
and the .env file disabled (the autouse isolation fixture), so it observes only the values it
writes and sets. require_startup_warmup is the slice's only key; the retired flat names and the
deleted fields are never read, and a deleted key in a file fails the load naming it.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice, install_configuration_files
from infrastructure.directory.settings import DirectorySettings, get_directory_settings
from server.configuration.loader import CONFIG_DIR, TomlConfigurationFiles

pytestmark = pytest.mark.unit

RETIRED_NAMES = (
    "DIRECTORY_PROVIDER",
    "DIRECTORY_REQUIRE_STARTUP_WARMUP",
    "DIRECTORY_CACHE_TTL_SECONDS",
    "DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS",
)
DELETED_KEYS = ("provider", "cache_ttl_seconds", "startup_warmup_timeout_seconds", "startup_preload_groups")


@pytest.fixture(autouse=True)
def _directory_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove DIRECTORY variables, disable the .env file and clear the cached provider."""
    monkeypatch.setitem(DirectorySettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.upper().startswith("DIRECTORY_"):
            monkeypatch.delenv(key, raising=False)
    get_directory_settings.cache_clear()
    yield
    get_directory_settings.cache_clear()


def _install(tmp_path: Path, base: str = "[directory]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )


def test_directory_settings_is_a_slice_on_the_directory_table() -> None:
    """The slice reads [directory] with the DIRECTORY__ prefix and rejects unknown keys."""
    config = DirectorySettings.model_config

    assert issubclass(DirectorySettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("directory",)
    assert config.get("env_prefix") == "DIRECTORY__"
    assert config.get("extra") == "forbid"


def test_require_startup_warmup_is_the_only_key() -> None:
    """Every other former field is deleted, so the slice offers no key a reader could not honour."""
    assert tuple(DirectorySettings.model_fields) == ("require_startup_warmup",)


def test_the_default_is_no_startup_warmup(tmp_path: Path) -> None:
    _install(tmp_path)

    assert DirectorySettings().require_startup_warmup is False


def test_the_checked_in_base_file_sets_the_default() -> None:
    """base.toml carries the key with its default so the table is never empty."""
    install_configuration_files(TomlConfigurationFiles(environment="ci", paths=(CONFIG_DIR / "base.toml",)))

    assert DirectorySettings().require_startup_warmup is False


def test_a_file_sets_the_key(tmp_path: Path) -> None:
    _install(
        tmp_path,
        base="[directory]\nrequire_startup_warmup = false\n",
        environment="[directory]\nrequire_startup_warmup = true\n",
    )

    assert DirectorySettings().require_startup_warmup is True


def test_the_prefixed_environment_name_overrides_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path, base="[directory]\nrequire_startup_warmup = false\n")
    monkeypatch.setenv("DIRECTORY__REQUIRE_STARTUP_WARMUP", "true")

    assert DirectorySettings().require_startup_warmup is True


@pytest.mark.parametrize("key", DELETED_KEYS)
def test_a_deleted_key_in_a_file_fails_the_load_naming_it(tmp_path: Path, key: str) -> None:
    _install(tmp_path, base=f"[directory]\n{key} = 1\n")

    with pytest.raises(ConfigurationError, match=key):
        DirectorySettings()


def test_an_unknown_key_in_a_file_fails_the_load_naming_it(tmp_path: Path) -> None:
    _install(tmp_path, base="[directory]\nrequire_startup_warmop = true\n")

    with pytest.raises(ConfigurationError, match="require_startup_warmop"):
        DirectorySettings()


@pytest.mark.parametrize("name", RETIRED_NAMES)
def test_the_retired_flat_names_are_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """The old unprefixed names neither set the key nor fail the load."""
    _install(tmp_path)
    monkeypatch.setenv(name, "true" if name.endswith("WARMUP") else "retired")

    assert DirectorySettings().require_startup_warmup is False


def test_the_provider_is_cached() -> None:
    assert get_directory_settings() is get_directory_settings()
