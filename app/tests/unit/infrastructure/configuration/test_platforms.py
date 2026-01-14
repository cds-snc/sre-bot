"""Unit tests for platform infrastructure settings."""

import pytest

from infrastructure.configuration.infrastructure.platforms import (
    SlackPlatformSettings,
    TeamsPlatformSettings,
    DiscordPlatformSettings,
    PlatformsSettings,
)


@pytest.mark.unit
class TestSlackPlatformSettings:
    """Test SlackPlatformSettings configuration."""

    def test_default_values(self):
        """Test SlackPlatformSettings with default values."""
        settings = SlackPlatformSettings()

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

        settings = SlackPlatformSettings()

        assert settings.SOCKET_MODE is False


@pytest.mark.unit
class TestTeamsPlatformSettings:
    """Test TeamsPlatformSettings configuration."""

    def test_default_values(self):
        """Test TeamsPlatformSettings with default values."""
        settings = TeamsPlatformSettings()

        assert settings.ENABLED is False
        assert settings.APP_ID is None
        assert settings.APP_PASSWORD is None
        assert settings.TENANT_ID is None

    def test_enabled_with_credentials(self, monkeypatch):
        """Test TeamsPlatformSettings with enabled and credentials set."""
        monkeypatch.setenv("TEAMS_ENABLED", "true")
        monkeypatch.setenv("TEAMS_APP_ID", "test-app-id")
        monkeypatch.setenv("TEAMS_APP_PASSWORD", "test-password")
        monkeypatch.setenv("TEAMS_TENANT_ID", "test-tenant-id")

        settings = TeamsPlatformSettings()

        assert settings.ENABLED is True
        assert settings.APP_ID == "test-app-id"
        assert settings.APP_PASSWORD == "test-password"
        assert settings.TENANT_ID == "test-tenant-id"


@pytest.mark.unit
class TestDiscordPlatformSettings:
    """Test DiscordPlatformSettings configuration."""

    def test_default_values(self):
        """Test DiscordPlatformSettings with default values."""
        settings = DiscordPlatformSettings()

        assert settings.ENABLED is False
        assert settings.BOT_TOKEN is None
        assert settings.APPLICATION_ID is None
        assert settings.PUBLIC_KEY is None

    def test_enabled_with_credentials(self, monkeypatch):
        """Test DiscordPlatformSettings with enabled and credentials set."""
        monkeypatch.setenv("DISCORD_ENABLED", "true")
        monkeypatch.setenv("DISCORD_BOT_TOKEN", "test-bot-token")
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "123456789")
        monkeypatch.setenv("DISCORD_PUBLIC_KEY", "test-public-key")

        settings = DiscordPlatformSettings()

        assert settings.ENABLED is True
        assert settings.BOT_TOKEN == "test-bot-token"
        assert settings.APPLICATION_ID == "123456789"
        assert settings.PUBLIC_KEY == "test-public-key"


@pytest.mark.unit
class TestPlatformsSettings:
    """Test PlatformsSettings container."""

    def test_default_all_platforms_disabled(self):
        """Test PlatformsSettings with all platforms disabled by default."""
        settings = PlatformsSettings()

        assert settings.slack.ENABLED is False
        assert settings.teams.ENABLED is False
        assert settings.discord.ENABLED is False

    def test_nested_settings_initialization(self):
        """Test PlatformsSettings initializes nested settings objects."""
        settings = PlatformsSettings()

        assert isinstance(settings.slack, SlackPlatformSettings)
        assert isinstance(settings.teams, TeamsPlatformSettings)
        assert isinstance(settings.discord, DiscordPlatformSettings)

    def test_enable_slack_only(self, monkeypatch):
        """Test enabling only Slack platform."""
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-token")

        settings = PlatformsSettings()

        assert settings.slack.ENABLED is True
        assert settings.teams.ENABLED is False
        assert settings.discord.ENABLED is False

    def test_enable_multiple_platforms(self, monkeypatch):
        """Test enabling multiple platforms simultaneously."""
        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("TEAMS_ENABLED", "true")
        monkeypatch.setenv("DISCORD_ENABLED", "true")

        settings = PlatformsSettings()

        assert settings.slack.ENABLED is True
        assert settings.teams.ENABLED is True
        assert settings.discord.ENABLED is True

    def test_slack_settings_accessible(self, monkeypatch):
        """Test accessing Slack settings through PlatformsSettings."""
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")

        settings = PlatformsSettings()

        assert settings.slack.BOT_TOKEN == "xoxb-test"

    def test_teams_settings_accessible(self, monkeypatch):
        """Test accessing Teams settings through PlatformsSettings."""
        monkeypatch.setenv("TEAMS_APP_ID", "teams-app-id")

        settings = PlatformsSettings()

        assert settings.teams.APP_ID == "teams-app-id"

    def test_discord_settings_accessible(self, monkeypatch):
        """Test accessing Discord settings through PlatformsSettings."""
        monkeypatch.setenv("DISCORD_APPLICATION_ID", "123456")

        settings = PlatformsSettings()

        assert settings.discord.APPLICATION_ID == "123456"


@pytest.mark.unit
class TestMainSettingsIntegration:
    """Test PlatformsSettings integration with main Settings class."""

    def test_platforms_in_main_settings(self, monkeypatch):
        """Test that platforms settings are accessible from main Settings."""
        from infrastructure.configuration.settings import Settings

        # Clear any cached settings
        from infrastructure.services.providers import get_settings

        get_settings.cache_clear()

        monkeypatch.setenv("SLACK_ENABLED", "true")
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-main-test")

        settings = Settings()

        assert hasattr(settings, "platforms")
        assert settings.platforms.slack.ENABLED is True
        assert settings.platforms.slack.BOT_TOKEN == "xoxb-main-test"

        # Clean up
        get_settings.cache_clear()

    def test_all_platforms_accessible_from_main(self, monkeypatch):
        """Test all platform settings accessible from main Settings."""
        from infrastructure.configuration.settings import Settings
        from infrastructure.services.providers import get_settings

        get_settings.cache_clear()

        settings = Settings()

        # All platform sub-settings should exist
        assert hasattr(settings.platforms, "slack")
        assert hasattr(settings.platforms, "teams")
        assert hasattr(settings.platforms, "discord")

        get_settings.cache_clear()
