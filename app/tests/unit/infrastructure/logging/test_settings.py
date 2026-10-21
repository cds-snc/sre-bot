"""Unit tests for the infrastructure.logging settings slice.

LoggingSettings reads the [logging] table of the checked-in configuration files
(installed by the root conftest for ENVIRONMENT=ci) with LOGGING__ environment
overrides. The production test installs base.toml and production.toml from
app/config through the real loader, so it shows what production runs with.
The .env file is disabled where an environment value is asserted.
"""

import pytest

from contracts.configuration import ConfigurationSlice, install_configuration_files
from infrastructure.logging.settings import LoggingSettings, get_logging_settings
from server.configuration import load_configuration_files

pytestmark = pytest.mark.unit


class TestLoggingSettingsSlice:
    """LoggingSettings is a configuration-file slice owning the [logging] table."""

    def test_is_a_configuration_slice_for_the_logging_table(self):
        config = LoggingSettings.model_config
        assert issubclass(LoggingSettings, ConfigurationSlice)
        assert config.get("toml_table_header") == ("logging",)
        assert config.get("env_prefix") == "LOGGING__"
        assert config.get("extra") == "forbid"

    def test_production_files_give_info_level_and_no_extra_keys(self):
        """Production log output is unchanged: the level stays INFO and no extra keys are redacted."""
        install_configuration_files(load_configuration_files("production"))

        settings = LoggingSettings(_env_file=None)

        assert settings.log_level == "INFO"
        assert settings.redaction_extra_keys == ()


class TestLoggingSettingsEnvParsing:
    """LOGGING__<FIELD> environment variables override the files."""

    def test_reads_log_level_from_env(self, monkeypatch):
        monkeypatch.setenv("LOGGING__LOG_LEVEL", "DEBUG")
        assert LoggingSettings(_env_file=None).log_level == "DEBUG"

    def test_reads_redaction_extra_keys_from_env_as_json_array(self, monkeypatch):
        monkeypatch.setenv("LOGGING__REDACTION_EXTRA_KEYS", '["ssn", "custom_secret"]')
        assert LoggingSettings(_env_file=None).redaction_extra_keys == ("ssn", "custom_secret")

    def test_old_bare_names_are_not_read(self, monkeypatch):
        """No alias: LOG_LEVEL and REDACTION_EXTRA_KEYS no longer configure logging."""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        monkeypatch.setenv("REDACTION_EXTRA_KEYS", '["ssn"]')

        settings = LoggingSettings(_env_file=None)

        assert settings.log_level == "INFO"
        assert settings.redaction_extra_keys == ()


class TestGetLoggingSettingsSingleton:
    """get_logging_settings() is a cached singleton provider."""

    def test_get_logging_settings_returns_singleton(self):
        get_logging_settings.cache_clear()
        assert get_logging_settings() is get_logging_settings()
        get_logging_settings.cache_clear()
