"""Platform provider infrastructure settings.

Configuration for collaboration platform integrations (Slack, etc.).
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import SettingsConfigDict

from infrastructure.configuration.base import InfrastructureSettings


class SlackPlatformSettings(InfrastructureSettings):
    """Slack platform provider settings.

    Environment Variables:
        SLACK_ENABLED: Enable Slack provider (default: False)
        SLACK_SOCKET_MODE: Use Socket Mode vs HTTP webhooks (default: True)
        SLACK_APP_TOKEN: Slack app-level token (xapp-...) for Socket Mode
        SLACK_BOT_TOKEN: Slack bot token (xoxb-...)
        SLACK_SIGNING_SECRET: Slack signing secret for webhook verification

    Example:
        ```python
        from infrastructure.configuration import get_settings

        settings = get_settings()

        if settings.platforms.slack.ENABLED:
            bot_token = settings.platforms.slack.BOT_TOKEN
        ```
    """

    model_config = SettingsConfigDict(env_prefix="SLACK_")

    ENABLED: bool = Field(
        default=False,
        description="Enable Slack platform provider (set SLACK_ENABLED=true to enable)",
    )

    SOCKET_MODE: bool = Field(
        default=True,
        description="Use Socket Mode (True) or HTTP webhooks (False)",
    )

    APP_TOKEN: Optional[str] = Field(
        default=None,
        description="Slack app-level token (xapp-...) for Socket Mode",
    )

    BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Slack bot token (xoxb-...) for API calls",
    )

    SIGNING_SECRET: Optional[str] = Field(
        default=None,
        description="Slack signing secret for webhook verification",
    )

    def validate_configuration(self) -> None:
        """Validate Slack platform configuration.

        Ensures either Socket Mode (APP_TOKEN) or HTTP webhooks (SIGNING_SECRET)
        is properly configured when the provider is enabled.

        Raises:
            ValueError: If configuration is invalid

        Example:
            >>> settings = SlackPlatformSettings(
            ...     ENABLED=True,
            ...     SOCKET_MODE=True,
            ...     APP_TOKEN="xapp-123",
            ...     BOT_TOKEN="xoxb-456"
            ... )
            >>> settings.validate_configuration()  # OK

            >>> settings = SlackPlatformSettings(ENABLED=True)
            >>> settings.validate_configuration()  # Raises ValueError
        """
        if not self.ENABLED:
            return  # Skip validation if disabled

        # BOT_TOKEN always required
        if not self.BOT_TOKEN:
            raise ValueError(
                "SLACK_BOT_TOKEN is required when Slack provider is enabled"
            )

        # Socket Mode: APP_TOKEN required
        if self.SOCKET_MODE:
            if not self.APP_TOKEN:
                raise ValueError(
                    "SLACK_APP_TOKEN is required when SOCKET_MODE is enabled. "
                    "Get an app-level token from https://api.slack.com/apps"
                )
        # HTTP Mode: SIGNING_SECRET required
        else:
            if not self.SIGNING_SECRET:
                raise ValueError(
                    "SLACK_SIGNING_SECRET is required when SOCKET_MODE is disabled (HTTP webhooks). "
                    "Find your signing secret at https://api.slack.com/apps → Basic Information"
                )

    @model_validator(mode="after")
    def _validate_config(self):
        """Automatically validate configuration after model initialization."""
        self.validate_configuration()
        return self


class PlatformsSettings(InfrastructureSettings):
    """Container for all platform provider settings.

    Groups settings for Slack and other providers.

    Example:
        ```python
        from infrastructure.configuration import get_settings

        settings = get_settings()

        # Check which platforms are enabled
        if settings.platforms.slack.ENABLED:
            # Initialize Slack provider

        ```
    """

    slack: SlackPlatformSettings = Field(
        default_factory=SlackPlatformSettings,
        description="Slack platform provider settings",
    )


@lru_cache(maxsize=1)
def get_platforms_settings() -> PlatformsSettings:
    """Singleton provider for platform provider infrastructure settings."""
    return PlatformsSettings()
