"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

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
]
