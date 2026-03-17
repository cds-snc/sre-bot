"""Unit tests for DirectorySettings configuration."""

from infrastructure.configuration.infrastructure.directory import DirectorySettings


class TestDirectorySettings:
    """DirectorySettings defaults and env alias behaviour."""

    def test_directory_settings_defaults(self):
        # Arrange / Act
        settings = DirectorySettings()

        # Assert
        assert settings.provider == "google"
        assert settings.require_startup_warmup is False
        assert settings.startup_preload_groups == []
        assert settings.cache_ttl_seconds == 60
        assert settings.managed_group_domain == ""
        assert settings.enforce_managed_group_email is True
        assert settings.startup_warmup_timeout_seconds == 2

    def test_directory_settings_from_env_vars(self, monkeypatch):
        # Arrange
        monkeypatch.setenv("DIRECTORY_PROVIDER", "entra_id")
        monkeypatch.setenv("DIRECTORY_REQUIRE_STARTUP_WARMUP", "false")
        monkeypatch.setenv("DIRECTORY_CACHE_TTL_SECONDS", "300")
        monkeypatch.setenv("DIRECTORY_MANAGED_GROUP_DOMAIN", "example.com")
        monkeypatch.setenv("DIRECTORY_ENFORCE_MANAGED_GROUP_EMAIL", "false")
        monkeypatch.setenv("DIRECTORY_STARTUP_WARMUP_TIMEOUT_SECONDS", "5")

        # Act
        settings = DirectorySettings()

        # Assert
        assert settings.provider == "entra_id"
        assert settings.require_startup_warmup is False
        assert settings.cache_ttl_seconds == 300
        assert settings.managed_group_domain == "example.com"
        assert settings.enforce_managed_group_email is False
        assert settings.startup_warmup_timeout_seconds == 5
