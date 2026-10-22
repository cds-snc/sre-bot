"""Unit tests for app-level settings singleton."""

import pytest
from pydantic import ValidationError

from infrastructure.configuration.app import AppSettings, get_app_settings


class TestAppSettings:
    """Test suite for AppSettings configuration."""

    def test_app_settings_defaults(self):
        """AppSettings should provide stable defaults."""
        settings = AppSettings()

        assert settings.git_sha == "Unknown"
        assert not hasattr(settings, "LOG_LEVEL")

    def test_app_settings_no_legacy_prefix_attribute(self):
        """Legacy command-prefix setting is no longer exposed on app settings."""
        settings = AppSettings()

        assert not hasattr(settings, "PREFIX")

    def test_app_settings_ignores_extra_env_vars(self, monkeypatch):
        """Unknown environment variables should be ignored during settings loading."""
        monkeypatch.setenv("UNKNOWN_VAR", "x")

        settings = AppSettings()

        assert not hasattr(settings, "UNKNOWN_VAR")

    def test_app_settings_singleton_returns_same_instance(self):
        """Provider should return same cached singleton instance."""
        get_app_settings.cache_clear()

        instance1 = get_app_settings()
        instance2 = get_app_settings()

        assert instance1 is instance2


class TestAppSettingsEnvironment:
    """Behavior tests for the ENVIRONMENT setting."""

    def test_environment_missing_fails_naming_it(self, monkeypatch):
        """ENVIRONMENT has no default: without it (and with no .env file read), construction fails naming the key."""
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        with pytest.raises(ValidationError) as exc_info:
            AppSettings(_env_file=None)

        assert exc_info.value.errors()[0]["loc"] == ("environment",)
        assert exc_info.value.errors()[0]["type"] == "missing"

    @pytest.mark.parametrize("value", ["local", "ci", "production"])
    def test_environment_all_valid_values(self, value):
        """Each environment the app runs in constructs successfully."""
        settings = AppSettings(ENVIRONMENT=value)

        assert value == settings.environment

    @pytest.mark.parametrize("value", ["uat", "dev", "staging", ""])
    def test_environment_invalid_value_raises_validation_error(self, value):
        """Values outside local, ci and production (including the retired dev and staging) fail validation."""
        with pytest.raises(ValidationError):
            AppSettings(ENVIRONMENT=value)


class TestAppSettingsWebhookMaxBodyBytes:
    """Behavior tests for the webhook body-size cap setting."""

    def test_webhook_max_body_bytes_default(self):
        """Default cap should match AWS SNS's own 256 KiB publish-size ceiling."""
        settings = AppSettings()

        assert settings.webhook_max_body_bytes == 262_144

    def test_webhook_max_body_bytes_configurable_via_env(self, monkeypatch):
        """The cap should be overridable via the WEBHOOK_MAX_BODY_BYTES env var."""
        monkeypatch.setenv("WEBHOOK_MAX_BODY_BYTES", "1024")

        settings = AppSettings()

        assert settings.webhook_max_body_bytes == 1024

    def test_contract_app_settings_has_no_legacy_production_property(self):
        """Contract: AppSettings no longer exposes the legacy production shim."""
        settings = AppSettings(ENVIRONMENT="production")
        legacy_attr = "is" + "_production"

        assert not hasattr(settings, legacy_attr)
