"""Vendor settings for the Azure Sentinel log client.

Exposes ``SentinelSettings`` and the cached ``get_sentinel_settings()`` provider. Each field
reads the environment variable of the same name.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class SentinelSettings(BaseSettings):
    """Azure Sentinel configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    SENTINEL_CUSTOMER_ID: str | None = None
    SENTINEL_LOG_TYPE: str = "DevSREBot"
    SENTINEL_SHARED_KEY: str | None = None


@lru_cache(maxsize=1)
def get_sentinel_settings() -> SentinelSettings:
    """Singleton provider for Azure Sentinel integration settings."""
    return SentinelSettings()
