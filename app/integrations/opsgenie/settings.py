"""Vendor settings for the OpsGenie API client.

Exposes ``OpsGenieSettings`` and the cached ``get_opsgenie_settings()`` provider. Each field
reads the environment variable of the same name.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class OpsGenieSettings(BaseSettings):
    """OpsGenie API configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    OPSGENIE_INTEGRATIONS_KEY: str | None = None


@lru_cache(maxsize=1)
def get_opsgenie_settings() -> OpsGenieSettings:
    """Singleton provider for OpsGenie integration settings."""
    return OpsGenieSettings()
