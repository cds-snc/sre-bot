"""Unit tests for DirectorySettings configuration."""

from infrastructure.directory.settings import DirectorySettings, get_directory_settings


class TestDirectorySettings:
    """DirectorySettings defaults and env alias behaviour."""

    def test_directory_settings_defaults(self):
        # Arrange / Act — _env_file=None prevents pydantic-settings from reading .env
        settings = DirectorySettings(_env_file=None)

        # Assert
        assert settings.provider == "google"
        assert settings.require_startup_warmup is False
        assert settings.startup_preload_groups == []
        assert settings.cache_ttl_seconds == 60
        assert settings.startup_warmup_timeout_seconds == 2

    def test_directory_settings_carry_no_managed_group_fields(self):
        # Act
        settings = DirectorySettings(_env_file=None)

        # Assert
        assert not hasattr(settings, "managed_group_domain")
        assert not hasattr(settings, "managed_group_prefix")
        assert not hasattr(settings, "enforce_managed_group_email")

    def test_directory_settings_from_env_vars(self, monkeypatch):
        # Arrange
        monkeypatch.setenv("DIRECTORY_PROVIDER", "entra_id")
        monkeypatch.setenv("DIRECTORY_REQUIRE_STARTUP_WARMUP", "true")
        monkeypatch.setenv("DIRECTORY_CACHE_TTL_SECONDS", "300")
        monkeypatch.setenv("DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS", "5")

        # Act
        settings = DirectorySettings()

        # Assert
        assert settings.provider == "entra_id"
        assert settings.require_startup_warmup is True
        assert settings.cache_ttl_seconds == 300
        assert settings.startup_warmup_timeout_seconds == 5


class TestDirectorySettingsSingleton:
    """The accessor caches a single settings instance."""

    def test_singleton_returns_same_instance(self):
        # Arrange
        get_directory_settings.cache_clear()

        # Act / Assert
        assert get_directory_settings() is get_directory_settings()

    def test_has_required_model_config(self):
        # Act
        config = DirectorySettings.model_config

        # Assert
        assert config.get("env_file") == ".env"
        assert config.get("extra") == "ignore"
