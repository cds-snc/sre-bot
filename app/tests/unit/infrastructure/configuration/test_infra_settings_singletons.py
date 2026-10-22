"""Unit tests for infrastructure settings singleton providers."""

from infrastructure.configuration.infrastructure.retry import (
    RetrySettings,
    get_retry_settings,
)
from infrastructure.configuration.infrastructure.server import (
    DevSettings,
    ServerSettings,
    get_dev_settings,
    get_server_settings,
)


class TestServerSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_server_settings.cache_clear()
        assert get_server_settings() is get_server_settings()

    def test_has_required_model_config(self):
        config = ServerSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("BACKEND_URL", "http://example.com:9000")
        settings = ServerSettings()
        assert settings.backend_url == "http://example.com:9000"


class TestDevSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_dev_settings.cache_clear()
        assert get_dev_settings() is get_dev_settings()

    def test_has_required_model_config(self):
        config = DevSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_DEV_MSG_CHANNEL", "C_TEST123")
        settings = DevSettings()
        assert settings.slack_dev_msg_channel == "C_TEST123"


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
