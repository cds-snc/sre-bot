"""Unit tests for the conditional-write settings slice.

Covers the singleton provider, the IDEMPOTENCY_* environment variable names
and the defaults of the record and in-progress claim TTL fields.
"""

import pytest

from infrastructure.coordination.settings import (
    ConditionalWriteSettings,
    get_conditional_write_settings,
)

pytestmark = pytest.mark.unit


class TestConditionalWriteSettingsSingleton:
    """Conditional-write settings provider remains singleton-scoped."""

    def test_singleton_returns_same_instance(self):
        get_conditional_write_settings.cache_clear()
        assert get_conditional_write_settings() is get_conditional_write_settings()

    def test_has_required_model_config(self):
        config = ConditionalWriteSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_default_ttl_seconds_is_one_hour(self):
        settings = ConditionalWriteSettings()
        assert settings.idempotency_ttl_seconds == 3600

    def test_reads_ttl_seconds_from_env(self, monkeypatch):
        monkeypatch.setenv("IDEMPOTENCY_TTL_SECONDS", "7200")
        settings = ConditionalWriteSettings()
        assert settings.idempotency_ttl_seconds == 7200


class TestConditionalWriteInProgressTtlSetting:
    """New bounded in-progress claim TTL required for crashed-claimant takeover."""

    def test_default_in_progress_ttl_seconds(self):
        settings = ConditionalWriteSettings()
        assert settings.idempotency_in_progress_ttl_seconds == 300

    def test_reads_in_progress_ttl_seconds_from_env(self, monkeypatch):
        monkeypatch.setenv("IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS", "60")
        settings = ConditionalWriteSettings()
        assert settings.idempotency_in_progress_ttl_seconds == 60
