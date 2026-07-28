"""Unit tests for the infrastructure.logging settings slice (TASK-8).

Mirrors app/tests/unit/infrastructure/idempotency/test_idempotency_settings.py.
"""

import pytest
from infrastructure.logging.settings import LoggingSettings, get_logging_settings

pytestmark = pytest.mark.unit


class TestLoggingSettingsDefaults:
    """LoggingSettings default configuration."""

    def test_has_required_model_config(self):
        config = LoggingSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_logging_settings_defaults_to_empty_extra_keys(self):
        settings = LoggingSettings()
        assert settings.REDACTION_EXTRA_KEYS == ()


class TestLoggingSettingsEnvParsing:
    """REDACTION_EXTRA_KEYS is read from the environment as a JSON array."""

    def test_logging_settings_reads_redaction_extra_keys_from_env(self, monkeypatch):
        monkeypatch.setenv("REDACTION_EXTRA_KEYS", '["ssn", "custom_secret"]')
        settings = LoggingSettings()
        assert settings.REDACTION_EXTRA_KEYS == ("ssn", "custom_secret")


class TestGetLoggingSettingsSingleton:
    """get_logging_settings() is a cached singleton provider."""

    def test_get_logging_settings_returns_singleton(self):
        get_logging_settings.cache_clear()
        assert get_logging_settings() is get_logging_settings()
