"""Slack domain settings.

Canonical configuration for the infrastructure.slack package.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator

from infrastructure.configuration.base import IntegrationSettings


class SlackSettings(IntegrationSettings):
    """Slack transport and integration settings.

    Supports both legacy and new token field names to preserve behavior:
    - ``SLACK_BOT_TOKEN`` (preferred)
    - ``SLACK_TOKEN`` (legacy)
    """

    ENABLED: bool = Field(default=True, alias="SLACK_ENABLED")
    SOCKET_MODE: bool = Field(default=True, alias="SLACK_SOCKET_MODE")

    APP_TOKEN: Optional[str] = Field(default=None, alias="SLACK_APP_TOKEN")
    BOT_TOKEN: Optional[str] = Field(default=None, alias="SLACK_BOT_TOKEN")
    SLACK_TOKEN: Optional[str] = Field(default=None, alias="SLACK_TOKEN")
    SIGNING_SECRET: Optional[str] = Field(default=None, alias="SLACK_SIGNING_SECRET")

    INCIDENT_CHANNEL: str = Field(default="", alias="INCIDENT_CHANNEL")
    SLACK_SECURITY_USER_GROUP_ID: str = Field(
        default="",
        alias="SLACK_SECURITY_USER_GROUP_ID",
    )

    @property
    def effective_bot_token(self) -> Optional[str]:
        """Return bot token using preferred field then legacy fallback."""
        return self.BOT_TOKEN or self.SLACK_TOKEN

    @model_validator(mode="after")
    def _validate_when_enabled(self):
        if not self.ENABLED:
            return self

        if not self.effective_bot_token:
            raise ValueError(
                "SLACK_BOT_TOKEN (or legacy SLACK_TOKEN) is required when Slack is enabled"
            )

        if self.SOCKET_MODE and not self.APP_TOKEN:
            raise ValueError(
                "SLACK_APP_TOKEN is required when SLACK_SOCKET_MODE is enabled"
            )

        if not self.SOCKET_MODE and not self.SIGNING_SECRET:
            raise ValueError(
                "SLACK_SIGNING_SECRET is required when SLACK_SOCKET_MODE is disabled"
            )

        return self


@lru_cache(maxsize=1)
def get_slack_settings() -> SlackSettings:
    """Get application-scoped Slack settings singleton."""
    return SlackSettings()
