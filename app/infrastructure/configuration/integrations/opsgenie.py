"""OpsGenie integration settings."""

from pydantic import Field

from infrastructure.configuration.base import IntegrationSettings


class OpsGenieSettings(IntegrationSettings):
    """OpsGenie API configuration.

    Environment Variables:
        OPSGENIE_INTEGRATIONS_KEY: OpsGenie API integration key

    Example:
        ```python
        from infrastructure.configuration import settings

        api_key = settings.opsgenie.OPSGENIE_INTEGRATIONS_KEY
        ```
    """

    OPSGENIE_INTEGRATIONS_KEY: str | None = Field(
        default=None, alias="OPSGENIE_INTEGRATIONS_KEY"
    )
