"""Unit tests for the dedicated idempotency settings slice.

Covers the settings relocation from
infrastructure.configuration.infrastructure.idempotency to
infrastructure.idempotency.settings, plus the new bounded in-progress
claim TTL field.
"""

import pytest

from infrastructure.idempotency.settings import (
    IdempotencySettings,
    get_idempotency_settings,
)

pytestmark = pytest.mark.unit


class TestIdempotencySettingsSingleton:
    """Idempotency settings provider remains singleton-scoped."""

    def test_singleton_returns_same_instance(self):
        get_idempotency_settings.cache_clear()
        assert get_idempotency_settings() is get_idempotency_settings()

    def test_has_required_model_config(self):
        config = IdempotencySettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_default_ttl_seconds_is_one_hour(self):
        settings = IdempotencySettings()
        assert settings.IDEMPOTENCY_TTL_SECONDS == 3600

    def test_reads_ttl_seconds_from_env(self, monkeypatch):
        monkeypatch.setenv("IDEMPOTENCY_TTL_SECONDS", "7200")
        settings = IdempotencySettings()
        assert settings.IDEMPOTENCY_TTL_SECONDS == 7200


class TestIdempotencyInProgressTtlSetting:
    """New bounded in-progress claim TTL required for crashed-claimant takeover."""

    def test_default_in_progress_ttl_seconds(self):
        settings = IdempotencySettings()
        assert settings.IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS == 300

    def test_reads_in_progress_ttl_seconds_from_env(self, monkeypatch):
        monkeypatch.setenv("IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS", "60")
        settings = IdempotencySettings()
        assert settings.IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS == 60


class TestLegacyIdempotencySettingsLocationRemoved:
    """The old settings home must be gone once the migration lands."""

    def test_old_settings_module_no_longer_exists(self):
        with pytest.raises(ModuleNotFoundError):
            import infrastructure.configuration.infrastructure.idempotency  # noqa: F401
