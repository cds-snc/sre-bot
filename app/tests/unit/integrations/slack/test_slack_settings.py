"""Tests for `SlackSettings` and its `get_slack_settings()` provider.

Verifies vendor-credential scope (tokens, delivery mode, transport knobs),
env-var resolution, fail-fast validation for delivery-mode credentials,
the `@lru_cache` singleton contract, and the absence of domain fields.
"""

import pytest
from structlog.testing import capture_logs

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


class TestSlackSettingsDeliveryMode:
    """`SlackSettings` carries delivery-mode credentials and fail-fast validation."""

    def test_enabled_defaults_to_false(self):
        assert SlackSettings().enabled is False

    def test_socket_mode_defaults_to_true(self):
        assert SlackSettings().socket_mode is True

    def test_app_token_defaults_to_none(self):
        assert SlackSettings().app_token is None

    def test_signing_secret_defaults_to_none(self):
        assert SlackSettings().signing_secret is None

    def test_enabled_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-token")

        assert SlackSettings().enabled is True

    def test_socket_mode_false_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_SOCKET_MODE", "false")
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")

        assert SlackSettings().socket_mode is False

    def test_app_token_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-real-token")

        assert SlackSettings().app_token == "xapp-real-token"

    def test_signing_secret_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "abc123")

        assert SlackSettings().signing_secret == "abc123"


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

    def test_user_token_is_not_coupled_to_transport_validation(self, monkeypatch):
        monkeypatch.setenv("SLACK_USER_TOKEN", "xoxp-user-token")
        monkeypatch.setenv("SLACK_ENABLED", "false")

        settings = SlackSettings()

        assert settings.enabled is False
        assert settings.user_token == "xoxp-user-token"


class TestSlackSettingsFailFast:
    """Fail-fast validation fires when enabled but required credentials are absent."""

    def test_socket_mode_enabled_without_app_token_raises(self, monkeypatch):
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_SOCKET_MODE", "true")

        with pytest.raises(Exception, match="SLACK_APP_TOKEN"):
            SlackSettings()

    def test_http_events_enabled_without_signing_secret_raises(self, monkeypatch):
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_SOCKET_MODE", "false")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-x")

        with pytest.raises(Exception, match="SLACK_SIGNING_SECRET"):
            SlackSettings()

    def test_disabled_skips_credential_validation(self):
        # No APP_TOKEN or SIGNING_SECRET — should not raise because ENABLED=false.
        settings = SlackSettings(SLACK_ENABLED=False)

        assert settings.enabled is False

    def test_socket_mode_enabled_with_app_token_is_valid(self, monkeypatch):
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-token")

        settings = SlackSettings()

        assert settings.enabled is True
        assert settings.socket_mode is True

    def test_http_events_enabled_with_signing_secret_is_valid(self, monkeypatch):
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_SOCKET_MODE", "false")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "hex-secret")

        settings = SlackSettings()

        assert settings.socket_mode is False


class TestSlackSettingsSocketModeSigningSecretNotice:
    """Socket Mode surfaces missing signing-secret readiness as an info notice."""

    def test_enabled_socket_mode_without_signing_secret_logs_info_notice(self, monkeypatch):
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_SOCKET_MODE", "true")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-token")

        with capture_logs() as entries:
            settings = SlackSettings()

        assert settings.enabled is True
        assert settings.socket_mode is True
        notice_entries = [entry for entry in entries if entry.get("event") == "slack_signing_secret_not_set_in_socket_mode"]
        assert notice_entries
        assert notice_entries[0].get("log_level") == "info"

    def test_enabled_socket_mode_with_signing_secret_logs_no_notice(self, monkeypatch):
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_TEAM_ID", "T0TEST")
        monkeypatch.setenv("SLACK_SOCKET_MODE", "true")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-token")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")

        with capture_logs() as entries:
            settings = SlackSettings()

        assert settings.enabled is True
        assert settings.socket_mode is True
        notice_entries = [entry for entry in entries if entry.get("event") == "slack_signing_secret_not_set_in_socket_mode"]
        assert notice_entries == []

    def test_disabled_socket_mode_without_signing_secret_logs_no_notice(self):
        with capture_logs() as entries:
            settings = SlackSettings(SLACK_ENABLED=False)

        assert settings.enabled is False
        notice_entries = [entry for entry in entries if entry.get("event") == "slack_signing_secret_not_set_in_socket_mode"]
        assert notice_entries == []


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
