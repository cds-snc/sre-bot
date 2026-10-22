"""Vendor settings for the Azure Sentinel log client.

Exposes ``SentinelSettings`` and the cached ``get_sentinel_settings()`` provider. Each field
reads the environment variable of the same name, matched case-insensitively.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class SentinelSettings(BaseSettings):
    """Azure Sentinel configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    sentinel_customer_id: str | None = None
    sentinel_log_type: str = "DevSREBot"
    sentinel_shared_key: str | None = None


@lru_cache(maxsize=1)
def get_sentinel_settings() -> SentinelSettings:
    """Singleton provider for Azure Sentinel integration settings."""
    return SentinelSettings()
