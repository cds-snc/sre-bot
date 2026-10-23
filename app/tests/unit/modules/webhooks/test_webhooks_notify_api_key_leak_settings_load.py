"""Unit tests for the [notify_api_key_leak] slice beside the API-key-leak handler."""

import pytest

from contracts.configuration import ConfigurationError, install_configuration_files
from modules.webhooks.patterns.aws_sns_notification.settings import (
    NotifyApiKeyLeakSettings,
    get_notify_api_key_leak_settings,
)
from server.configuration import load_configuration_files

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTIFY_API_KEY_LEAK__CHANNEL_ID", raising=False)
    monkeypatch.delenv("NOTIFY_API_KEY_LEAK__ONCALL_GROUP_ID", raising=False)
    get_notify_api_key_leak_settings.cache_clear()
    yield
    get_notify_api_key_leak_settings.cache_clear()


@pytest.mark.parametrize(
    ("environment", "channel_id", "oncall_group_id"),
    [("local", "C033L7RGCT0", ""), ("ci", "C033L7RGCT0", ""), ("production", "CNWA63606", "S0BNW0G8CFK")],
)
def test_values_per_environment(environment: str, channel_id: str, oncall_group_id: str) -> None:
    """Each environment file chooses the channel and the on-call group."""
    install_configuration_files(load_configuration_files(environment))

    settings = NotifyApiKeyLeakSettings()

    assert (settings.channel_id, settings.oncall_group_id) == (channel_id, oncall_group_id)


def test_environment_variable_overrides_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """NOTIFY_API_KEY_LEAK__CHANNEL_ID beats the file value."""
    monkeypatch.setenv("NOTIFY_API_KEY_LEAK__CHANNEL_ID", "COVERRIDE")

    assert NotifyApiKeyLeakSettings().channel_id == "COVERRIDE"


def test_unknown_key_is_forbidden() -> None:
    """The table holds channel_id and oncall_group_id only."""
    with pytest.raises(ConfigurationError, match="not_a_key"):
        NotifyApiKeyLeakSettings(not_a_key="x")  # type: ignore[call-arg]


def test_provider_returns_singleton() -> None:
    """The provider caches the slice for the process."""
    assert get_notify_api_key_leak_settings() is get_notify_api_key_leak_settings()
