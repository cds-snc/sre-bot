"""GC Notify integration settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import IntegrationSettings


class NotifySettings(IntegrationSettings):
    """GC Notify API configuration.

    Environment Variables:
        NOTIFY_SRE_USER_NAME: GC Notify service account username
        NOTIFY_SRE_CLIENT_SECRET: GC Notify service account secret
        NOTIFY_API_URL: GC Notify API endpoint URL

    Example:
        ```python
        from infrastructure.configuration.integrations.notify import get_notify_settings

        settings = get_notify_settings()

        api_url = settings.NOTIFY_API_URL
        username = settings.NOTIFY_SRE_USER_NAME
        ```
    """

    NOTIFY_SRE_USER_NAME: str | None = Field(default=None, alias="NOTIFY_SRE_USER_NAME")
    NOTIFY_SRE_CLIENT_SECRET: str | None = Field(
        default=None, alias="NOTIFY_SRE_CLIENT_SECRET"
    )
    NOTIFY_API_URL: str = Field(default="", alias="NOTIFY_API_URL")


@lru_cache(maxsize=1)
def get_notify_settings() -> NotifySettings:
    """Singleton provider for GC Notify integration settings."""
    return NotifySettings()
