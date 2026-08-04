"""OpsGenie integration settings."""

from functools import lru_cache

from pydantic import Field

from infrastructure.configuration.base import IntegrationSettings


class OpsGenieSettings(IntegrationSettings):
    """OpsGenie API configuration.

    Environment Variables:
        OPSGENIE_INTEGRATIONS_KEY: OpsGenie API integration key

    Example:
        ```python
        from infrastructure.configuration.integrations.opsgenie import get_opsgenie_settings

        settings = get_opsgenie_settings()

        api_key = settings.OPSGENIE_INTEGRATIONS_KEY
        ```
    """

    OPSGENIE_INTEGRATIONS_KEY: str | None = Field(default=None, alias="OPSGENIE_INTEGRATIONS_KEY")


@lru_cache(maxsize=1)
def get_opsgenie_settings() -> OpsGenieSettings:
    """Singleton provider for OpsGenie integration settings."""
    return OpsGenieSettings()
