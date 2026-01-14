"""Platform provider infrastructure settings.

Configuration for collaboration platform integrations (Slack, Teams, Discord).
"""

from typing import Optional

from pydantic import Field
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
        from infrastructure.services import get_settings

        settings = get_settings()

        if settings.platforms.slack.ENABLED:
            bot_token = settings.platforms.slack.BOT_TOKEN
        ```
    """

    model_config = SettingsConfigDict(env_prefix="SLACK_")

    ENABLED: bool = Field(
        default=False,
        description="Enable Slack platform provider",
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


class TeamsPlatformSettings(InfrastructureSettings):
    """Microsoft Teams platform provider settings.

    Environment Variables:
        TEAMS_ENABLED: Enable Teams provider (default: False)
        TEAMS_APP_ID: Microsoft Teams app ID
        TEAMS_APP_PASSWORD: Microsoft Teams app password
        TEAMS_TENANT_ID: Azure AD tenant ID

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        if settings.platforms.teams.ENABLED:
            app_id = settings.platforms.teams.APP_ID
        ```
    """

    model_config = SettingsConfigDict(env_prefix="TEAMS_")

    ENABLED: bool = Field(
        default=False,
        description="Enable Microsoft Teams platform provider",
    )

    APP_ID: Optional[str] = Field(
        default=None,
        description="Microsoft Teams app ID",
    )

    APP_PASSWORD: Optional[str] = Field(
        default=None,
        description="Microsoft Teams app password/client secret",
    )

    TENANT_ID: Optional[str] = Field(
        default=None,
        description="Azure AD tenant ID",
    )

    def validate_configuration(self) -> None:
        """Validate Teams platform configuration.

        Ensures APP_ID and APP_PASSWORD are configured when provider is enabled.

        Raises:
            ValueError: If configuration is invalid

        Example:
            >>> settings = TeamsPlatformSettings(
            ...     ENABLED=True,
            ...     APP_ID="12345678-1234-1234-1234-123456789012",
            ...     APP_PASSWORD="secret"
            ... )
            >>> settings.validate_configuration()  # OK
        """
        if not self.ENABLED:
            return  # Skip validation if disabled

        if not self.APP_ID:
            raise ValueError(
                "TEAMS_APP_ID is required when Teams provider is enabled. "
                "Register your app at https://dev.botframework.com/bots/new"
            )

        if not self.APP_PASSWORD:
            raise ValueError(
                "TEAMS_APP_PASSWORD is required when Teams provider is enabled. "
                "Get app password from Azure AD app registration"
            )


class DiscordPlatformSettings(InfrastructureSettings):
    """Discord platform provider settings.

    Environment Variables:
        DISCORD_ENABLED: Enable Discord provider (default: False)
        DISCORD_BOT_TOKEN: Discord bot token
        DISCORD_APPLICATION_ID: Discord application ID
        DISCORD_PUBLIC_KEY: Discord public key for interaction verification

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        if settings.platforms.discord.ENABLED:
            token = settings.platforms.discord.BOT_TOKEN
        ```
    """

    model_config = SettingsConfigDict(env_prefix="DISCORD_")

    ENABLED: bool = Field(
        default=False,
        description="Enable Discord platform provider",
    )

    BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Discord bot token",
    )

    APPLICATION_ID: Optional[str] = Field(
        default=None,
        description="Discord application ID",
    )

    PUBLIC_KEY: Optional[str] = Field(
        default=None,
        description="Discord public key for interaction verification",
    )

    def validate_configuration(self) -> None:
        """Validate Discord platform configuration.

        ⚠️ Discord support is out of scope - this is a placeholder.

        Raises:
            NotImplementedError: Always raises since Discord is not implemented
        """
        if self.ENABLED:
            raise NotImplementedError(
                "Discord platform provider is not implemented. "
                "Discord support is out of scope for the current release."
            )


class PlatformsSettings(InfrastructureSettings):
    """Container for all platform provider settings.

    Groups settings for Slack, Teams, and Discord providers.

    Example:
        ```python
        from infrastructure.services import get_settings

        settings = get_settings()

        # Check which platforms are enabled
        if settings.platforms.slack.ENABLED:
            # Initialize Slack provider

        if settings.platforms.teams.ENABLED:
            # Initialize Teams provider
        ```
    """

    slack: SlackPlatformSettings = Field(
        default_factory=SlackPlatformSettings,
        description="Slack platform provider settings",
    )

    teams: TeamsPlatformSettings = Field(
        default_factory=TeamsPlatformSettings,
        description="Microsoft Teams platform provider settings",
    )

    discord: DiscordPlatformSettings = Field(
        default_factory=DiscordPlatformSettings,
        description="Discord platform provider settings",
    )
