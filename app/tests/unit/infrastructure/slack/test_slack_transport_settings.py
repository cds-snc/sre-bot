"""Behavior tests for the Slack transport settings slice on the [slack_transport] table.

Settings are built under the installed configuration files; the checked-in
local and production files are installed explicitly where their values are asserted.
"""

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files
from infrastructure.slack.settings import SlackTransportSettings, get_slack_transport_settings
from server.configuration import load_configuration_files

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove both spellings so each test controls the environment and the provider cache."""
    monkeypatch.delenv("SLACK__COMMAND_PREFIX", raising=False)
    monkeypatch.delenv("SLACK_TRANSPORT__COMMAND_PREFIX", raising=False)
    get_slack_transport_settings.cache_clear()
    yield
    get_slack_transport_settings.cache_clear()


def test_command_prefix_is_empty_under_the_ci_files() -> None:
    """The base file sets an empty prefix and ci does not override it."""
    assert SlackTransportSettings().command_prefix == ""


def test_local_file_sets_the_dev_prefix() -> None:
    """local.toml gives developers the dev- prefix without any environment variable."""
    install_configuration_files(load_configuration_files("local"))

    assert SlackTransportSettings().command_prefix == "dev-"


def test_production_file_sets_no_prefix() -> None:
    """production.toml keeps the production commands unprefixed."""
    install_configuration_files(load_configuration_files("production"))

    assert SlackTransportSettings().command_prefix == ""


def test_prefixed_environment_variable_overrides_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """SLACK_TRANSPORT__COMMAND_PREFIX beats the file value."""
    monkeypatch.setenv("SLACK_TRANSPORT__COMMAND_PREFIX", "env-")

    assert SlackTransportSettings().command_prefix == "env-"


def test_former_slack_command_prefix_name_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """The retired SLACK__COMMAND_PREFIX name no longer reaches the field."""
    monkeypatch.setenv("SLACK__COMMAND_PREFIX", "old-")

    assert SlackTransportSettings().command_prefix == ""


def test_slice_declares_only_command_prefix_without_alias() -> None:
    """The table holds command_prefix alone and the field has no alias."""
    assert set(SlackTransportSettings.model_fields) == {"command_prefix"}
    field = SlackTransportSettings.model_fields["command_prefix"]
    assert field.alias is None
    assert field.validation_alias is None


def test_provider_returns_singleton_instance() -> None:
    """The provider returns the same settings instance per process."""
    assert get_slack_transport_settings() is get_slack_transport_settings()


def test_invalid_value_fails_validation() -> None:
    """A non-string prefix fails validation, naming the file and key."""
    with pytest.raises(ConfigurationError, match="command_prefix"):
        SlackTransportSettings(command_prefix=None)
