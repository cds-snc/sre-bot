"""Unit tests for platform infrastructure settings."""

import pytest

from infrastructure.configuration.infrastructure.platforms import (
    PlatformsSettings,
    SlackPlatformSettings,
)


@pytest.mark.unit
class TestSlackPlatformSettings:
    """Test SlackPlatformSettings configuration."""

    def test_default_values(self, monkeypatch):
        """Test SlackPlatformSettings with default values (unset optional fields)."""
        # Remove optional token env vars to test defaults
        monkeypatch.delenv("SLACK_APP_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)

        settings = SlackPlatformSettings(_env_file=None)

        assert settings.ENABLED is False
        assert settings.SOCKET_MODE is True
        assert settings.APP_TOKEN is None
        assert settings.BOT_TOKEN is None
        assert settings.SIGNING_SECRET is None

    def test_enabled_with_tokens(self, monkeypatch):
        """Test SlackPlatformSettings with enabled and tokens set."""
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")

        settings = SlackPlatformSettings()

        assert settings.ENABLED is True
        assert settings.APP_TOKEN == "xapp-test-token"
        assert settings.BOT_TOKEN == "xoxb-test-token"
        assert settings.SIGNING_SECRET == "test-secret"

    def test_socket_mode_false(self, monkeypatch):
        """Test SlackPlatformSettings with HTTP webhook mode."""
        monkeypatch.setenv("SLACK_SOCKET_MODE", "false")
        monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-signing-secret")

        settings = SlackPlatformSettings()

        assert settings.SOCKET_MODE is False


@pytest.mark.unit
class TestPlatformsSettings:
    """Test PlatformsSettings container."""

    def test_default_all_platforms_disabled(self):
        """Test PlatformsSettings with all platforms disabled by default."""
        settings = PlatformsSettings()

        assert settings.slack.ENABLED is False

    def test_nested_settings_initialization(self):
        """Test PlatformsSettings initializes nested settings objects."""
        settings = PlatformsSettings()

        assert isinstance(settings.slack, SlackPlatformSettings)

    def test_enable_slack_only(self, monkeypatch):
        """Test enabling only Slack platform."""
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-token")

        settings = PlatformsSettings()

        assert settings.slack.ENABLED is True

    def test_enable_multiple_platforms(self, monkeypatch):
        """Test enabling multiple platforms simultaneously."""
        monkeypatch.setenv("SLACK_ENABLED", "true")

        settings = PlatformsSettings()

        assert settings.slack.ENABLED is True

    def test_slack_settings_accessible(self, monkeypatch):
        """Test accessing Slack settings through PlatformsSettings."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")

        settings = PlatformsSettings()

        assert settings.slack.BOT_TOKEN == "xoxb-test"
