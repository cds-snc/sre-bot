"""Tests for platform configuration validation."""

import pytest

from infrastructure.configuration.infrastructure.platforms import (
    DiscordPlatformSettings,
    SlackPlatformSettings,
    TeamsPlatformSettings,
)


class TestSlackPlatformSettings:
    """Tests for Slack platform configuration validation."""

    def test_validation_skipped_when_disabled(self):
        """Should skip validation when provider is disabled."""
        settings = SlackPlatformSettings(ENABLED=False)
        settings.validate_configuration()  # Should not raise

    def test_socket_mode_requires_app_token(self, monkeypatch):
        """Should require APP_TOKEN when Socket Mode is enabled."""
        # Set APP_TOKEN to empty/None in environment
        monkeypatch.setenv("SLACK__APP_TOKEN", "")
        monkeypatch.setenv("PLATFORMS__SLACK__APP_TOKEN", "")

        # Pydantic validates on __init__, so exception raised during construction
        with pytest.raises(ValueError, match="SLACK_APP_TOKEN is required"):
            SlackPlatformSettings(
                ENABLED=True,
                SOCKET_MODE=True,
                BOT_TOKEN="xoxb-123",
                APP_TOKEN="",  # Explicitly set to empty
            )

    def test_http_mode_requires_signing_secret(self, monkeypatch):
        """Should require SIGNING_SECRET when HTTP webhooks are enabled."""
        # Set SIGNING_SECRET to empty in environment
        monkeypatch.setenv("SLACK__SIGNING_SECRET", "")
        monkeypatch.setenv("PLATFORMS__SLACK__SIGNING_SECRET", "")

        # Pydantic validates on __init__, so exception raised during construction
        with pytest.raises(ValueError, match="SLACK_SIGNING_SECRET is required"):
            SlackPlatformSettings(
                ENABLED=True,
                SOCKET_MODE=False,
                BOT_TOKEN="xoxb-123",
                SIGNING_SECRET="",  # Explicitly set to empty
            )

    def test_always_requires_bot_token(self, monkeypatch):
        """Should always require BOT_TOKEN when enabled."""
        # Set BOT_TOKEN to empty in environment
        monkeypatch.setenv("SLACK__BOT_TOKEN", "")
        monkeypatch.setenv("SLACK__SLACK_TOKEN", "")
        monkeypatch.setenv("PLATFORMS__SLACK__BOT_TOKEN", "")

        # Pydantic validates on __init__, so exception raised during construction
        with pytest.raises(ValueError, match="SLACK_BOT_TOKEN is required"):
            SlackPlatformSettings(
                ENABLED=True,
                SOCKET_MODE=True,
                APP_TOKEN="xapp-123",
                BOT_TOKEN="",  # Explicitly set to empty
            )

    def test_valid_socket_mode_configuration(self):
        """Should accept valid Socket Mode configuration."""
        settings = SlackPlatformSettings(
            ENABLED=True,
            SOCKET_MODE=True,
            APP_TOKEN="xapp-123",
            BOT_TOKEN="xoxb-456",
        )

        settings.validate_configuration()  # Should not raise

    def test_valid_http_mode_configuration(self):
        """Should accept valid HTTP webhook configuration."""
        settings = SlackPlatformSettings(
            ENABLED=True,
            SOCKET_MODE=False,
            BOT_TOKEN="xoxb-456",
            SIGNING_SECRET="abc123",
        )

        settings.validate_configuration()  # Should not raise


class TestTeamsPlatformSettings:
    """Tests for Teams platform configuration validation."""

    def test_validation_skipped_when_disabled(self):
        """Should skip validation when provider is disabled."""
        settings = TeamsPlatformSettings(ENABLED=False)
        settings.validate_configuration()  # Should not raise

    def test_requires_app_id(self):
        """Should require APP_ID when enabled."""
        settings = TeamsPlatformSettings(
            ENABLED=True,
            APP_PASSWORD="secret",
            # Missing APP_ID
        )

        with pytest.raises(ValueError, match="TEAMS_APP_ID is required"):
            settings.validate_configuration()

    def test_requires_app_password(self):
        """Should require APP_PASSWORD when enabled."""
        settings = TeamsPlatformSettings(
            ENABLED=True,
            APP_ID="12345678-1234-1234-1234-123456789012",
            # Missing APP_PASSWORD
        )

        with pytest.raises(ValueError, match="TEAMS_APP_PASSWORD is required"):
            settings.validate_configuration()

    def test_valid_configuration(self):
        """Should accept valid Teams configuration."""
        settings = TeamsPlatformSettings(
            ENABLED=True,
            APP_ID="12345678-1234-1234-1234-123456789012",
            APP_PASSWORD="secret",
            TENANT_ID="87654321-4321-4321-4321-210987654321",
        )

        settings.validate_configuration()  # Should not raise


class TestDiscordPlatformSettings:
    """Tests for Discord platform configuration validation."""

    def test_validation_skipped_when_disabled(self):
        """Should skip validation when provider is disabled."""
        settings = DiscordPlatformSettings(ENABLED=False)
        settings.validate_configuration()  # Should not raise

    def test_raises_not_implemented_when_enabled(self):
        """Should raise NotImplementedError when Discord is enabled."""
        settings = DiscordPlatformSettings(
            ENABLED=True,
            BOT_TOKEN="token",
            APPLICATION_ID="app-id",
            PUBLIC_KEY="key",
        )

        with pytest.raises(
            NotImplementedError, match="Discord platform provider is not implemented"
        ):
            settings.validate_configuration()
