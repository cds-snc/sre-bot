"""Unit tests for the [server] slice and the HostInfo built from it."""

import importlib
from dataclasses import dataclass
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files, uninstall_configuration_files
from server.configuration import IdentitySettings, ServerSettings, build_host_info, load_configuration_files

pytestmark = pytest.mark.unit


@dataclass(frozen=True)
class _Files:
    environment: str
    paths: tuple[Path, ...]


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "SERVER__PUBLIC_BASE_URL",
        "SERVER__SRE_TEST_CHANNEL_ID",
        "SERVER__WEBHOOK_MAX_BODY_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)


def test_base_defaults_under_the_ci_files() -> None:
    """The ci files give the base defaults, with an empty test channel."""
    settings = ServerSettings()

    assert settings.public_base_url == "http://127.0.0.1:8000"
    assert settings.sre_test_channel_id == ""
    assert settings.webhook_max_body_bytes == 262_144


def test_production_file_values() -> None:
    """production.toml names the public address and the test channel."""
    install_configuration_files(load_configuration_files("production"))

    settings = ServerSettings()

    assert settings.public_base_url == "https://sre-bot.cdssandbox.xyz"
    assert settings.sre_test_channel_id == "C033L7RGCT0"


def test_prefixed_environment_variable_beats_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """SERVER__PUBLIC_BASE_URL overrides the file value."""
    monkeypatch.setenv("SERVER__PUBLIC_BASE_URL", "https://override.example")

    assert ServerSettings().public_base_url == "https://override.example"


def test_unknown_key_in_the_table_fails_naming_it(tmp_path: Path) -> None:
    """A key outside the slice fails, and the message names the key."""
    base = tmp_path / "base.toml"
    environment = tmp_path / "ci.toml"
    base.write_text('[server]\npublic_base_url = "http://x"\nnot_a_key = 1\n')
    environment.write_text("")
    install_configuration_files(_Files("ci", (base, environment)))

    with pytest.raises(Exception, match="not_a_key"):
        ServerSettings()


def test_building_before_install_raises() -> None:
    """The slice cannot be built before the configuration phase."""
    uninstall_configuration_files()

    with pytest.raises(ConfigurationError):
        ServerSettings()


def test_fields_have_no_alias() -> None:
    """Every field reads only its prefixed name."""
    for field in ServerSettings.model_fields.values():
        assert field.alias is None
        assert field.validation_alias is None
    assert set(ServerSettings.model_fields) == {"public_base_url", "sre_test_channel_id", "webhook_max_body_bytes"}


def test_build_host_info_maps_identity_and_server() -> None:
    """HostInfo carries the identity's environment and sha and the server's public address."""
    identity = IdentitySettings(environment="production", git_sha="abc")
    server = ServerSettings(public_base_url="https://sre.example")

    info = build_host_info(identity, server)

    assert (info.environment, info.git_sha, info.public_base_url) == ("production", "abc", "https://sre.example")


@pytest.mark.parametrize(
    "module",
    ["infrastructure.configuration.app", "infrastructure.configuration.infrastructure.server"],
)
def test_retired_settings_modules_no_longer_exist(module: str) -> None:
    """AppSettings, the old ServerSettings and DevSettings are gone."""
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)
