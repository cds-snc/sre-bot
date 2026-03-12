"""Unit tests for DirectorySettings configuration."""

from infrastructure.configuration.infrastructure.directory import DirectorySettings


class TestDirectorySettings:
    """DirectorySettings defaults and env alias behaviour."""

    def test_directory_settings_defaults(self):
        # Arrange / Act
        settings = DirectorySettings()

        # Assert
        assert settings.provider == "google"
        assert settings.require_startup_warmup is True
        assert settings.startup_preload_groups == []
        assert settings.cache_ttl_seconds == 60

    def test_directory_settings_from_env_vars(self, monkeypatch):
        # Arrange
        monkeypatch.setenv("DIRECTORY_PROVIDER", "entra_id")
        monkeypatch.setenv("DIRECTORY_REQUIRE_STARTUP_WARMUP", "false")
        monkeypatch.setenv("DIRECTORY_CACHE_TTL_SECONDS", "300")

        # Act
        settings = DirectorySettings()

        # Assert
        assert settings.provider == "entra_id"
        assert settings.require_startup_warmup is False
        assert settings.cache_ttl_seconds == 300
