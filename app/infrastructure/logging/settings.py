"""Structured logging settings owned by the logging infrastructure."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import InfrastructureSettings


class LoggingSettings(InfrastructureSettings):
    """Configuration for structured logging redaction.

    Environment Variables:
        REDACTION_EXTRA_KEYS: JSON array of extra deny-list key substrings.
    """

    REDACTION_EXTRA_KEYS: tuple[str, ...] = Field(default=(), alias="REDACTION_EXTRA_KEYS")


@lru_cache(maxsize=1)
def get_logging_settings() -> LoggingSettings:
    """Singleton provider for logging settings."""
    return LoggingSettings()
