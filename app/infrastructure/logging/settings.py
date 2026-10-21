"""Structured logging settings owned by the logging infrastructure."""

from functools import lru_cache

from pydantic_settings import SettingsConfigDict

from contracts.configuration import ConfigurationSlice


class LoggingSettings(ConfigurationSlice):
    """Root log level and extra redaction keys, read from the [logging] table.

    Environment overrides: LOGGING__LOG_LEVEL, LOGGING__REDACTION_EXTRA_KEYS (JSON array
    of extra deny-list key substrings).
    """

    model_config = SettingsConfigDict(toml_table_header=("logging",), env_prefix="LOGGING__")

    log_level: str = "INFO"
    redaction_extra_keys: tuple[str, ...] = ()


@lru_cache(maxsize=1)
def get_logging_settings() -> LoggingSettings:
    """Singleton provider for logging settings."""
    return LoggingSettings()
