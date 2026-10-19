"""Vendor settings for the Trello API client.

Exposes ``TrelloSettings`` and the cached ``get_trello_settings()`` provider. Each field
reads the environment variable of the same name.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class TrelloSettings(BaseSettings):
    """Trello API configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    TRELLO_APP_KEY: str | None = None
    TRELLO_TOKEN: str | None = None
    TRELLO_ATIP_BOARD: str | None = None


@lru_cache(maxsize=1)
def get_trello_settings() -> TrelloSettings:
    """Singleton provider for Trello integration settings."""
    return TrelloSettings()
