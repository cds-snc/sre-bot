"""GC Notify integration settings."""

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
        from infrastructure.services import get_settings

        settings = get_settings()

        api_url = settings.notify.NOTIFY_API_URL
        username = settings.notify.NOTIFY_SRE_USER_NAME
        ```
    """

    NOTIFY_SRE_USER_NAME: str | None = Field(default=None, alias="NOTIFY_SRE_USER_NAME")
    NOTIFY_SRE_CLIENT_SECRET: str | None = Field(
        default=None, alias="NOTIFY_SRE_CLIENT_SECRET"
    )
    NOTIFY_API_URL: str = Field(default="", alias="NOTIFY_API_URL")
