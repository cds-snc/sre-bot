"""Unit tests for app-level settings singleton."""

import pytest
from pydantic import ValidationError

from infrastructure.configuration.app import AppSettings, get_app_settings


class TestAppSettings:
    """Test suite for AppSettings configuration."""

    def test_app_settings_defaults(self):
        """AppSettings should provide stable defaults."""
        settings = AppSettings()

        assert settings.PREFIX == ""
        assert settings.LOG_LEVEL == "INFO"
        assert settings.GIT_SHA == "Unknown"

    def test_app_settings_is_production_when_environment_production(self):
        """is_production should be True when ENVIRONMENT is production."""
        settings = AppSettings(ENVIRONMENT="production")

        assert settings.is_production is True

    def test_app_settings_is_not_production_when_environment_non_production(self):
        """is_production should be False when ENVIRONMENT is non-production."""
        settings = AppSettings(ENVIRONMENT="dev")

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


class TestAppSettingsEnvironment:
    """Behavior tests for ENVIRONMENT and DEV_BYPASS_ENABLED settings."""

    def test_environment_default_is_local(self, monkeypatch):
        """Default environment should be local."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        settings = AppSettings()

        assert settings.ENVIRONMENT == "local"

    @pytest.mark.parametrize(
        "value",
        ["local", "ci", "dev", "staging", "production"],
    )
    def test_environment_all_valid_values(self, value):
        """All accepted environment values should construct successfully."""
        settings = AppSettings(ENVIRONMENT=value)

        assert settings.ENVIRONMENT == value

    def test_environment_invalid_value_raises_validation_error(self):
        """Unknown environment values should fail validation at settings construction."""
        with pytest.raises(ValidationError):
            AppSettings(ENVIRONMENT="uat")

    def test_dev_bypass_enabled_default_false(self):
        """DEV_BYPASS_ENABLED should default to False."""
        settings = AppSettings()

        assert settings.DEV_BYPASS_ENABLED is False

    def test_dev_bypass_enabled_can_be_set_true(self):
        """DEV_BYPASS_ENABLED should be configurable to True."""
        settings = AppSettings(DEV_BYPASS_ENABLED=True)

        assert settings.DEV_BYPASS_ENABLED is True

    def test_is_production_shim_true_when_production(self):
        """is_production should be True when ENVIRONMENT is production."""
        settings = AppSettings(ENVIRONMENT="production")

        assert settings.is_production is True

    def test_is_production_shim_false_when_local(self):
        """is_production should be False when ENVIRONMENT is local."""
        settings = AppSettings(ENVIRONMENT="local")

        assert settings.is_production is False

    def test_is_production_shim_false_when_ci(self):
        """is_production should be False when ENVIRONMENT is ci."""
        settings = AppSettings(ENVIRONMENT="ci")

        assert settings.is_production is False

    def test_contract_app_settings_has_no_is_production_property(self):
        """Contract: AppSettings no longer exposes an is_production shim."""
        settings = AppSettings(ENVIRONMENT="production")

        assert not hasattr(settings, "is_production")
