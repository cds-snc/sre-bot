"""Tests for platform configuration validation."""

import pytest

from infrastructure.configuration.infrastructure.platforms import (
    SlackPlatformSettings,
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
