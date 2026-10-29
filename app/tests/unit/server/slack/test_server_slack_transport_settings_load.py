"""Behavior tests for the Slack transport settings slice on the [slack_transport] table.

Settings are built under the installed configuration files; the checked-in
local and production files are installed explicitly where their values are asserted.
"""

import tomllib
from pathlib import Path

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files
from server.configuration import load_configuration_files
from server.slack.settings import SlackTransportSettings, get_slack_transport_settings

pytestmark = pytest.mark.unit

CONFIG_DIRECTORY = Path(__file__).resolve().parents[4] / "config"

_NAMES = (
    "SLACK_TRANSPORT__COMMAND_PREFIX",
    "SLACK_TRANSPORT__ENABLED",
    "SLACK_TRANSPORT__SOCKET_MODE",
)


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the slice's variables so each test controls the environment and the provider cache."""
    for name in _NAMES:
        monkeypatch.delenv(name, raising=False)
    get_slack_transport_settings.cache_clear()
    yield
    get_slack_transport_settings.cache_clear()


def test_ci_files_leave_the_transport_off_in_socket_mode_without_prefix() -> None:
    """The base file switches the transport off in Socket Mode with an empty prefix, and ci keeps it."""
    settings = SlackTransportSettings()

    assert settings.enabled is False
    assert settings.socket_mode is True
    assert settings.command_prefix == ""


def test_local_file_switches_the_transport_on_with_the_dev_prefix() -> None:
    """local.toml runs the transport with the dev- prefix without any environment variable."""
    install_configuration_files(load_configuration_files("local"))

    settings = SlackTransportSettings()

    assert settings.enabled is True
    assert settings.command_prefix == "dev-"


def test_production_file_switches_the_transport_on_without_prefix() -> None:
    """production.toml runs the transport unprefixed: a missing key would boot Slack off unnoticed."""
    install_configuration_files(load_configuration_files("production"))

    settings = SlackTransportSettings()

    assert settings.enabled is True
    assert settings.socket_mode is True
    assert settings.command_prefix == ""


def test_socket_mode_is_written_only_in_the_base_file() -> None:
    """Socket Mode is the default everywhere: no environment file sets it."""
    for path in sorted(CONFIG_DIRECTORY.glob("*.toml")):
        table = tomllib.loads(path.read_text()).get("slack_transport", {})
        assert ("socket_mode" in table) == (path.name == "base.toml"), path.name


def test_prefixed_environment_variables_override_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """SLACK_TRANSPORT__<FIELD> beats the file value."""
    monkeypatch.setenv("SLACK_TRANSPORT__COMMAND_PREFIX", "env-")
    monkeypatch.setenv("SLACK_TRANSPORT__ENABLED", "true")
    monkeypatch.setenv("SLACK_TRANSPORT__SOCKET_MODE", "false")

    settings = SlackTransportSettings()

    assert settings.command_prefix == "env-"
    assert settings.enabled is True
    assert settings.socket_mode is False


def test_slice_declares_its_three_fields_without_alias() -> None:
    """The table holds enabled, socket_mode and command_prefix, none with an alias."""
    assert set(SlackTransportSettings.model_fields) == {"enabled", "socket_mode", "command_prefix"}
    for field in SlackTransportSettings.model_fields.values():
        assert field.alias is None
        assert field.validation_alias is None


def test_provider_returns_singleton_instance() -> None:
    """The provider returns the same settings instance per process."""
    assert get_slack_transport_settings() is get_slack_transport_settings()


def test_invalid_value_fails_validation() -> None:
    """A non-string prefix fails validation, naming the key."""
    with pytest.raises(ConfigurationError, match="command_prefix"):
        SlackTransportSettings(command_prefix=None)


def test_unknown_key_fails_validation() -> None:
    """A misspelled key in the table fails naming it, since the slice forbids extras."""
    with pytest.raises(ConfigurationError, match="socket_mod"):
        SlackTransportSettings(socket_mod=True)  # type: ignore[call-arg]
