"""Unit tests for loading the coordination slice from the [coordination] table.

Each test installs a base and a local file from tmp_path with every COORDINATION variable
removed and the .env file disabled (the autouse isolation fixture), so it observes only
the values it writes and sets. The slice holds the table name and the two TTLs under keys that do
not repeat the table, and an unknown key in the table fails the load naming it.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice, install_configuration_files
from infrastructure.coordination.settings import ConditionalWriteSettings, get_conditional_write_settings
from server.configuration.loader import CONFIG_DIR, TomlConfigurationFiles

pytestmark = pytest.mark.unit

DEFAULTS = {"table_name": "sre_bot_idempotency", "record_ttl_seconds": 3600, "in_progress_ttl_seconds": 300}


@pytest.fixture(autouse=True)
def _coordination_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove COORDINATION variables, disable the .env file and clear the cached provider."""
    monkeypatch.setitem(ConditionalWriteSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.upper().startswith("COORDINATION_"):
            monkeypatch.delenv(key, raising=False)
    get_conditional_write_settings.cache_clear()
    yield
    get_conditional_write_settings.cache_clear()


def _install(tmp_path: Path, base: str = "[coordination]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )


def _values(settings: ConditionalWriteSettings) -> dict[str, object]:
    return {name: getattr(settings, name) for name in DEFAULTS}


def test_coordination_settings_is_a_slice_on_the_coordination_table() -> None:
    """The slice reads [coordination] with the COORDINATION__ prefix and rejects unknown keys."""
    config = ConditionalWriteSettings.model_config

    assert issubclass(ConditionalWriteSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("coordination",)
    assert config.get("env_prefix") == "COORDINATION__"
    assert config.get("extra") == "forbid"


def test_the_keys_do_not_repeat_the_table() -> None:
    assert tuple(ConditionalWriteSettings.model_fields) == tuple(DEFAULTS)


def test_the_defaults_are_the_terraform_table_and_todays_ttls(tmp_path: Path) -> None:
    _install(tmp_path)

    assert _values(ConditionalWriteSettings()) == DEFAULTS


def test_the_checked_in_base_file_sets_the_defaults() -> None:
    """base.toml carries every key with its default, the table name being the one terraform creates."""
    install_configuration_files(TomlConfigurationFiles(environment="ci", paths=(CONFIG_DIR / "base.toml",)))

    assert _values(ConditionalWriteSettings()) == DEFAULTS


def test_a_file_sets_the_keys(tmp_path: Path) -> None:
    _install(
        tmp_path,
        base="[coordination]\nrecord_ttl_seconds = 3600\n",
        environment='[coordination]\ntable_name = "elsewhere"\nrecord_ttl_seconds = 60\nin_progress_ttl_seconds = 5\n',
    )

    assert _values(ConditionalWriteSettings()) == {
        "table_name": "elsewhere",
        "record_ttl_seconds": 60,
        "in_progress_ttl_seconds": 5,
    }


def test_the_prefixed_environment_names_override_the_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path, base="[coordination]\nin_progress_ttl_seconds = 300\n")
    monkeypatch.setenv("COORDINATION__TABLE_NAME", "from_env")
    monkeypatch.setenv("COORDINATION__IN_PROGRESS_TTL_SECONDS", "45")

    settings = ConditionalWriteSettings()

    assert settings.table_name == "from_env"
    assert settings.in_progress_ttl_seconds == 45


@pytest.mark.parametrize("key", ["idempotency_ttl_seconds", "idempotency_in_progress_ttl_seconds", "record_ttl"])
def test_an_unknown_key_in_a_file_fails_the_load_naming_it(tmp_path: Path, key: str) -> None:
    """The former field names are unknown keys too, so a stale file cannot set them silently."""
    _install(tmp_path, base=f"[coordination]\n{key} = 1\n")

    with pytest.raises(ConfigurationError, match=key):
        ConditionalWriteSettings()


def test_the_provider_is_cached() -> None:
    assert get_conditional_write_settings() is get_conditional_write_settings()
