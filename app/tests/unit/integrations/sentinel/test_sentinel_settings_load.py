"""Unit tests for loading the Azure Sentinel vendor slice.

Each test installs a base and a local file from tmp_path with every SENTINEL_* and SENTINEL__*
variable removed and the .env file disabled (the autouse isolation fixture), so it observes only
the values it writes and sets. The log type is a file key; the workspace id and the shared key
are read only from SENTINEL__CUSTOMER_ID and SENTINEL__SHARED_KEY.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, ConfigurationSlice, install_configuration_files
from integrations.sentinel.settings import SentinelSettings, get_sentinel_settings
from server.configuration.loader import TomlConfigurationFiles, load_configuration_files

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _sentinel_env_isolation(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove every Sentinel variable, disable the .env file and clear the cached provider."""
    monkeypatch.setitem(SentinelSettings.model_config, "env_file", None)
    for key in tuple(os.environ):
        if key.startswith("SENTINEL_"):
            monkeypatch.delenv(key, raising=False)
    get_sentinel_settings.cache_clear()
    yield
    get_sentinel_settings.cache_clear()


def _install(tmp_path: Path, base: str = "[sentinel]\n", environment: str = "") -> None:
    (tmp_path / "base.toml").write_text(base, encoding="utf-8")
    (tmp_path / "local.toml").write_text(environment, encoding="utf-8")
    install_configuration_files(
        TomlConfigurationFiles(environment="local", paths=(tmp_path / "base.toml", tmp_path / "local.toml"))
    )


def test_sentinel_settings_is_a_slice_on_the_sentinel_table() -> None:
    """The slice reads [sentinel] with the SENTINEL__ prefix and rejects unknown keys."""
    config = SentinelSettings.model_config

    assert issubclass(SentinelSettings, ConfigurationSlice)
    assert config.get("toml_table_header") == ("sentinel",)
    assert config.get("env_prefix") == "SENTINEL__"
    assert config.get("extra") == "forbid"


def test_sentinel_settings_getter_returns_one_cached_instance(tmp_path: Path) -> None:
    _install(tmp_path)

    assert get_sentinel_settings() is get_sentinel_settings()


def test_nothing_set_leaves_sentinel_unconfigured_with_the_default_log_type(tmp_path: Path) -> None:
    _install(tmp_path)

    settings = SentinelSettings()

    assert settings.customer_id == ""
    assert settings.shared_key.get_secret_value() == ""
    assert settings.log_type == "DevSREBot"


def test_the_environment_file_sets_the_log_type(tmp_path: Path) -> None:
    _install(tmp_path, environment='[sentinel]\nlog_type = "ProductionLogs"\n')

    assert SentinelSettings().log_type == "ProductionLogs"


def test_the_credentials_come_from_their_environment_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install(tmp_path)
    monkeypatch.setenv("SENTINEL__CUSTOMER_ID", "workspace-0001")
    monkeypatch.setenv("SENTINEL__SHARED_KEY", "c2hhcmVkLWtleQ==")

    settings = SentinelSettings()

    assert settings.customer_id == "workspace-0001"
    assert settings.shared_key.get_secret_value() == "c2hhcmVkLWtleQ=="


def test_the_credentials_never_appear_in_repr_or_str(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The workspace id is non-public and the key a secret: neither is rendered with the slice."""
    _install(tmp_path)
    monkeypatch.setenv("SENTINEL__CUSTOMER_ID", "workspace-render")
    monkeypatch.setenv("SENTINEL__SHARED_KEY", "key-render")

    settings = SentinelSettings()

    for rendered in (repr(settings), str(settings)):
        assert "workspace-render" not in rendered
        assert "key-render" not in rendered


def test_an_unknown_key_in_the_table_fails_the_slice(tmp_path: Path) -> None:
    _install(tmp_path, base="[sentinel]\nunknown = 1\n")

    with pytest.raises(ConfigurationError, match="unknown"):
        SentinelSettings()


def test_production_sets_the_log_type() -> None:
    """production.toml sets the Sentinel log type the production workspace expects."""
    install_configuration_files(load_configuration_files("production"))

    assert SentinelSettings().log_type == "SREBot"
