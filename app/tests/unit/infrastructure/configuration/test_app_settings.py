"""Unit tests for app-level settings singleton."""

from infrastructure.configuration.app import AppSettings, get_app_settings


class TestAppSettings:
    """Test suite for AppSettings configuration."""

    def test_app_settings_defaults(self):
        """AppSettings should provide stable defaults."""
        settings = AppSettings()

        assert settings.PREFIX == ""
        assert settings.LOG_LEVEL == "INFO"
        assert settings.GIT_SHA == "Unknown"

    def test_app_settings_is_production_when_prefix_empty(self):
        """is_production should be True when PREFIX is empty."""
        settings = AppSettings(PREFIX="")

        assert settings.is_production is True

    def test_app_settings_is_not_production_when_prefix_set(self):
        """is_production should be False when PREFIX is set."""
        settings = AppSettings(PREFIX="dev")

        assert settings.is_production is False

    def test_app_settings_ignores_extra_env_vars(self, monkeypatch):
        """Unknown environment variables should be ignored during settings loading."""
        monkeypatch.setenv("UNKNOWN_VAR", "x")

        settings = AppSettings()

        assert settings.PREFIX == ""

    def test_app_settings_singleton_returns_same_instance(self):
        """Provider should return same cached singleton instance."""
        get_app_settings.cache_clear()

        instance1 = get_app_settings()
        instance2 = get_app_settings()

        assert instance1 is instance2

    def test_app_settings_reads_from_env(self, monkeypatch):
        """Environment variables should override defaults."""
        monkeypatch.setenv("PREFIX", "staging")

        settings = AppSettings()

        assert settings.PREFIX == "staging"
