"""Vendor settings for the GC Notify API client.

Exposes ``NotifySettings`` and the cached ``get_notify_settings()`` provider. Each field
reads the environment variable of the same name, matched case-insensitively.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class NotifySettings(BaseSettings):
    """GC Notify API configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    notify_sre_user_name: str | None = None
    notify_sre_client_secret: str | None = None
    notify_api_url: str = ""


@lru_cache(maxsize=1)
def get_notify_settings() -> NotifySettings:
    """Singleton provider for GC Notify integration settings."""
    return NotifySettings()
