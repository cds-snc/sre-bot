"""Tests for `SlackSettings` and its `get_slack_settings()` provider.

Verifies vendor-credential scope (tokens, transport knobs), env-var
resolution, the absence of the transport switches (the [slack_transport] slice
holds them and the configuration phase runs the cross-slice rules), the
`@lru_cache` singleton contract, and the absence of domain fields.
"""

import pytest

from integrations.slack.settings import SlackSettings, get_slack_settings

pytestmark = pytest.mark.unit


class TestSlackSettingsFields:
    """Fields exposed by `SlackSettings`."""

    def test_defaults_resolve_when_env_is_empty(self):
        settings = SlackSettings()

        assert settings.bot_token == ""
        assert settings.request_timeout_seconds == 10
        assert settings.retry_max_attempts == 2

    def test_bot_token_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-real-token")

        settings = SlackSettings()

        assert settings.bot_token == "xoxb-real-token"

    def test_request_timeout_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_REQUEST_TIMEOUT_SECONDS", "25")

        settings = SlackSettings()

        assert settings.request_timeout_seconds == 25

    def test_retry_max_attempts_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_RETRY_MAX_ATTEMPTS", "5")

        settings = SlackSettings()

        assert settings.retry_max_attempts == 5


class TestSlackSettingsDeliveryModeCredentials:
    """`SlackSettings` carries the delivery-mode credentials, never the transport switches."""

    def test_app_token_defaults_to_none(self):
        assert SlackSettings().app_token is None

    def test_signing_secret_defaults_to_none(self):
        assert SlackSettings().signing_secret is None

    def test_app_token_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-real-token")

        assert SlackSettings().app_token == "xapp-real-token"

    def test_signing_secret_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "abc123")

        assert SlackSettings().signing_secret == "abc123"

    def test_transport_switches_are_not_fields(self):
        assert "enabled" not in SlackSettings.model_fields
        assert "socket_mode" not in SlackSettings.model_fields

    def test_retired_switch_names_are_ignored_without_validation(self, monkeypatch):
        """A stale SLACK_ENABLED with no team id or app token no longer fails the slice."""
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_SOCKET_MODE", "false")
        monkeypatch.delenv("SLACK_TEAM_ID", raising=False)
        monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)

        settings = SlackSettings(_env_file=None)

        assert settings.tenant is None


class TestSlackSettingsUserToken:
    """Slack user token is a dedicated vendor credential for user-group writes."""

    def test_user_token_defaults_to_empty_string(self):
        settings = SlackSettings()

        assert settings.user_token == ""

    def test_user_token_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-user-token")

        settings = SlackSettings()

        assert settings.user_token == "xoxp-user-token"

    def test_user_token_does_not_appear_in_repr(self, monkeypatch):
        monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-user-token")

        settings = SlackSettings()
        settings_repr = repr(settings)

        assert "user_token" not in settings_repr
        assert "xoxp-user-token" not in settings_repr


class TestSlackSettingsScope:
    """`SlackSettings` carries vendor transport fields only; domain fields are absent."""

    @pytest.mark.parametrize(
        "field",
        [
            "INCIDENT_CHANNEL",
            "SLACK_SECURITY_USER_GROUP_ID",
            "SLACK_NOTIFY_MGMT_USER_GROUP_ID",
        ],
    )
    def test_domain_fields_are_absent(self, field):
        assert not hasattr(SlackSettings(), field)


class TestGetSlackSettingsProvider:
    """`get_slack_settings()` caches a single instance per process."""

    def test_returns_a_slacksettings_instance(self):
        assert isinstance(get_slack_settings(), SlackSettings)

    def test_is_a_singleton_across_calls(self):
        first = get_slack_settings()
        second = get_slack_settings()

        assert first is second

    def test_cache_clear_yields_a_fresh_instance(self):
        first = get_slack_settings()
        get_slack_settings.cache_clear()
        second = get_slack_settings()

        assert first is not second
