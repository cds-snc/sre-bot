"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from typing import cast

from infrastructure.services.dependencies import (
    SettingsDep,
    IdentityServiceDep,
    JWKSManagerDep,
    AWSClientsDep,
    GoogleWorkspaceClientsDep,
    MaxMindClientDep,
    EventDispatcherDep,
    TranslationServiceDep,
    IdempotencyServiceDep,
    ResilienceServiceDep,
    NotificationServiceDep,
    CommandServiceDep,
    PersistenceServiceDep,
    PlatformServiceDep,
    SlackClientDep,
    TeamsClientDep,
    DiscordClientDep,
)
from infrastructure.services.providers import (
    get_settings,
    get_identity_service,
    get_jwks_manager,
    get_aws_clients,
    get_google_workspace_clients,
    get_maxmind_client,
    get_event_dispatcher,
    get_translation_service,
    get_idempotency_service,
    get_resilience_service,
    get_notification_service,
    get_command_service,
    get_persistence_service,
    get_platform_service,
    get_slack_client,
    get_teams_client,
    get_discord_client,
)

from infrastructure.platforms import (
    PlatformService,
    SlackPlatformProvider,
    TeamsPlatformProvider,
    DiscordPlatformProvider,
)


def get_slack_provider() -> SlackPlatformProvider:
    """Get Slack platform provider.

    Ergonomic accessor for Slack provider, replacing the two-step pattern.

    Returns:
        SlackPlatformProvider instance

    Raises:
        KeyError: If Slack provider not registered

    Example:
        >>> slack_provider = get_slack_provider()
        >>> slack_provider.register_command("geolocate", callback=handle_geolocate)
    """
    platform_service: PlatformService = get_platform_service()
    slack_provider = cast(SlackPlatformProvider, platform_service.get_provider("slack"))
    return slack_provider


def get_teams_provider() -> TeamsPlatformProvider:
    """Get Microsoft Teams platform provider.

    Ergonomic accessor for Teams provider.

    Returns:
        TeamsPlatformProvider instance

    Raises:
        KeyError: If Teams provider not registered

    Example:
        >>> teams_provider = get_teams_provider()
        >>> teams_provider.register_command("geolocate", callback=handle_geolocate)
    """
    platform_service: PlatformService = get_platform_service()
    teams_provider = cast(TeamsPlatformProvider, platform_service.get_provider("teams"))
    return teams_provider


def get_discord_provider() -> DiscordPlatformProvider:
    """Get Discord platform provider.

    Ergonomic accessor for Discord provider.

    Returns:
        DiscordPlatformProvider instance

    Raises:
        KeyError: If Discord provider not registered

    Example:
        >>> discord_provider = get_discord_provider()
        >>> discord_provider.register_command("geolocate", callback=handle_geolocate)
    """
    platform_service: PlatformService = get_platform_service()
    discord_provider = cast(
        DiscordPlatformProvider, platform_service.get_provider("discord")
    )
    return discord_provider


__all__ = [
    # Core dependencies
    "SettingsDep",
    "IdentityServiceDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "GoogleWorkspaceClientsDep",
    "MaxMindClientDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
    "NotificationServiceDep",
    "CommandServiceDep",
    "PersistenceServiceDep",
    "PlatformServiceDep",
    # Platform client facades
    "SlackClientDep",
    "TeamsClientDep",
    "DiscordClientDep",
    # Core providers
    "get_settings",
    "get_identity_service",
    "get_jwks_manager",
    "get_aws_clients",
    "get_google_workspace_clients",
    "get_maxmind_client",
    "get_event_dispatcher",
    "get_translation_service",
    "get_idempotency_service",
    "get_resilience_service",
    "get_notification_service",
    "get_command_service",
    "get_persistence_service",
    "get_platform_service",
    # Platform client providers
    "get_slack_client",
    "get_teams_client",
    "get_discord_client",
    # Platform provider accessors (ergonomic improvement)
    "get_slack_provider",
    "get_teams_provider",
    "get_discord_provider",
]
