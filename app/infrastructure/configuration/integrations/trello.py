"""Trello integration settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import IntegrationSettings


class TrelloSettings(IntegrationSettings):
    """Trello API configuration.

    Environment Variables:
        TRELLO_APP_KEY: Trello application API key
        TRELLO_TOKEN: Trello user token
        TRELLO_ATIP_BOARD: ATIP board ID

    Example:
        ```python
        from infrastructure.configuration.integrations.trello import get_trello_settings

        settings = get_trello_settings()

        app_key = settings.TRELLO_APP_KEY
        token = settings.TRELLO_TOKEN
        ```
    """

    TRELLO_APP_KEY: str | None = Field(default=None, alias="TRELLO_APP_KEY")
    TRELLO_TOKEN: str | None = Field(default=None, alias="TRELLO_TOKEN")
    TRELLO_ATIP_BOARD: str | None = Field(default=None, alias="TRELLO_ATIP_BOARD")


@lru_cache(maxsize=1)
def get_trello_settings() -> TrelloSettings:
    """Singleton provider for Trello integration settings."""
    return TrelloSettings()
