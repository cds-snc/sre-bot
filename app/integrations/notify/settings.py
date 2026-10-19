"""Vendor settings for the GC Notify API client.

Exposes ``NotifySettings`` and the cached ``get_notify_settings()`` provider. Each field
reads the environment variable of the same name.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class NotifySettings(BaseSettings):
    """GC Notify API configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    NOTIFY_SRE_USER_NAME: str | None = None
    NOTIFY_SRE_CLIENT_SECRET: str | None = None
    NOTIFY_API_URL: str = ""


@lru_cache(maxsize=1)
def get_notify_settings() -> NotifySettings:
    """Singleton provider for GC Notify integration settings."""
    return NotifySettings()
