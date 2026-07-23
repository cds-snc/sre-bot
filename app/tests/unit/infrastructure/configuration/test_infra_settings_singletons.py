"""Unit tests for infrastructure settings singleton providers (PR-3)."""

from infrastructure.configuration.infrastructure.directory import (
    DirectorySettings,
    get_directory_settings,
)
from infrastructure.configuration.infrastructure.idempotency import (
    IdempotencySettings,
    get_idempotency_settings,
)
from infrastructure.configuration.infrastructure.platforms import (
    PlatformsSettings,
    get_platforms_settings,
)
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
        assert settings.BACKEND_URL == "http://example.com:9000"


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
        assert settings.SLACK_DEV_MSG_CHANNEL == "C_TEST123"


class TestIdempotencySettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_idempotency_settings.cache_clear()
        assert get_idempotency_settings() is get_idempotency_settings()

    def test_has_required_model_config(self):
        config = IdempotencySettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("IDEMPOTENCY_TTL_SECONDS", "7200")
        settings = IdempotencySettings()
        assert settings.IDEMPOTENCY_TTL_SECONDS == 7200


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


class TestPlatformsSettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_platforms_settings.cache_clear()
        assert get_platforms_settings() is get_platforms_settings()

    def test_has_required_model_config(self):
        config = PlatformsSettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_default_providers_disabled(self):
        settings = PlatformsSettings()
        assert settings.slack.ENABLED is False


class TestDirectorySettingsSingleton:
    def test_singleton_returns_same_instance(self):
        get_directory_settings.cache_clear()
        assert get_directory_settings() is get_directory_settings()

    def test_has_required_model_config(self):
        config = DirectorySettings.model_config
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"

    def test_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("DIRECTORY_PROVIDER", "entra_id")
        settings = DirectorySettings()
        assert settings.provider == "entra_id"
