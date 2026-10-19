"""Vendor settings for the MaxMind GeoIP client.

Exposes ``MaxMindSettings`` and the cached ``get_maxmind_settings()`` provider. Each field
reads the environment variable of the same name.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MaxMindSettings(BaseSettings):
    """MaxMind GeoIP database configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    MAXMIND_DB_PATH: str = "./geodb/GeoLite2-City.mmdb"


@lru_cache(maxsize=1)
def get_maxmind_settings() -> MaxMindSettings:
    """Singleton provider for MaxMind integration settings."""
    return MaxMindSettings()
