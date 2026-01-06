"""Unit tests for infrastructure.configuration.settings module.

Tests cover:
- RetrySettings validation and defaults
- Settings class initialization
- Integration with Pydantic BaseSettings
"""

import pytest

from infrastructure.configuration.settings import RetrySettings, Settings
from infrastructure.services.providers import get_settings


class TestRetrySettings:
    """Test suite for RetrySettings configuration."""

    def test_retry_settings_defaults(self):
        """Test RetrySettings uses correct default values."""
        retry = RetrySettings()

        assert retry.enabled is True
        assert retry.backend == "memory"
        assert retry.max_attempts == 5
        assert retry.base_delay_seconds == 60
        assert retry.max_delay_seconds == 3600
        assert retry.batch_size == 10
        assert retry.claim_lease_seconds == 300

    def test_retry_settings_custom_values(self, monkeypatch):
        """Test RetrySettings accepts custom configuration."""
        monkeypatch.setenv("RETRY_ENABLED", "false")
        monkeypatch.setenv("RETRY_BACKEND", "dynamodb")
        monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "10")
        monkeypatch.setenv("RETRY_BASE_DELAY_SECONDS", "30")
        monkeypatch.setenv("RETRY_MAX_DELAY_SECONDS", "7200")
        monkeypatch.setenv("RETRY_BATCH_SIZE", "20")
        monkeypatch.setenv("RETRY_CLAIM_LEASE_SECONDS", "600")

        retry = RetrySettings()

        assert retry.enabled is False
        assert retry.backend == "dynamodb"
        assert retry.max_attempts == 10
        assert retry.base_delay_seconds == 30
        assert retry.max_delay_seconds == 7200
        assert retry.batch_size == 20
        assert retry.claim_lease_seconds == 600

    def test_retry_settings_partial_override(self, monkeypatch):
        """Test RetrySettings allows partial overrides."""
        monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "3")
        monkeypatch.setenv("RETRY_BACKEND", "sqs")

        retry = RetrySettings()

        assert retry.max_attempts == 3
        assert retry.backend == "sqs"
        # Defaults preserved
        assert retry.enabled is True
        assert retry.base_delay_seconds == 60

    def test_retry_settings_validation_positive_integers(self, monkeypatch):
        """Test RetrySettings validates positive integer constraints."""
        # Valid: positive integers
        monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "1")
        monkeypatch.setenv("RETRY_BATCH_SIZE", "1")
        retry = RetrySettings()
        assert retry.max_attempts == 1

        # Invalid: negative values should fail if validators exist
        # Note: Add validators to RetrySettings if this behavior is required

    def test_retry_settings_backend_values(self, monkeypatch):
        """Test RetrySettings accepts different backend types."""
        backends = ["memory", "dynamodb", "sqs", "redis"]
        for backend in backends:
            monkeypatch.setenv("RETRY_BACKEND", backend)
            retry = RetrySettings()
            assert retry.backend == backend


class TestSettings:
    """Test suite for main Settings class."""

    def test_settings_includes_retry_config(self):
        """Test Settings class includes retry configuration."""
        settings = Settings()

        assert hasattr(settings, "retry")
        assert isinstance(settings.retry, RetrySettings)

    def test_settings_retry_defaults(self):
        """Test Settings uses RetrySettings defaults."""
        settings = Settings()

        assert settings.retry.enabled is True
        assert settings.retry.backend == "memory"
        assert settings.retry.max_attempts == 5

    def test_settings_preserves_existing_config(self):
        """Test Settings still includes all existing configuration sections."""
        settings = Settings()

        # Verify major config sections still exist
        assert hasattr(settings, "slack")
        assert hasattr(settings, "aws")
        assert hasattr(settings, "server")
        assert hasattr(settings, "groups")


@pytest.mark.unit
class TestSettingsIntegration:
    """Integration tests for Settings with environment variables."""

    def test_settings_from_env_vars(self, monkeypatch):
        """Test Settings loads from environment variables."""
        monkeypatch.setenv("RETRY_ENABLED", "false")
        monkeypatch.setenv("RETRY_BACKEND", "dynamodb")
        monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "10")

        # Create new instance with environment variables
        retry = RetrySettings()

        # Verify settings loaded from environment
        assert retry.enabled is False
        assert retry.backend == "dynamodb"
        assert retry.max_attempts == 10

    def test_settings_singleton_behavior(self):
        """Test settings from get_settings returns singleton instance."""

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is not None
        assert isinstance(settings1, Settings)
        assert isinstance(settings2, Settings)
        assert settings1 is settings2  # Same instance (singleton)
