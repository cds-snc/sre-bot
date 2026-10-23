"""Unit tests for infrastructure settings singleton providers."""

from infrastructure.configuration.infrastructure.retry import (
    RetrySettings,
    get_retry_settings,
)


class TestRetrySettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_retry_settings.cache_clear()
        assert get_retry_settings() is get_retry_settings()

    def test_has_required_model_config(self):
        config = RetrySettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "10")
        settings = RetrySettings()
        assert settings.max_attempts == 10
