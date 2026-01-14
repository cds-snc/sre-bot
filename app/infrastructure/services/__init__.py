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
    EventDispatcherDep,
    TranslationServiceDep,
    IdempotencyServiceDep,
    ResilienceServiceDep,
    NotificationServiceDep,
    CommandServiceDep,
    PersistenceServiceDep,
    PlatformServiceDep,
)
from infrastructure.services.providers import (
    get_settings,
    get_identity_service,
    get_jwks_manager,
    get_aws_clients,
    get_google_workspace_clients,
    get_event_dispatcher,
    get_translation_service,
    get_idempotency_service,
    get_resilience_service,
    get_notification_service,
    get_command_service,
    get_persistence_service,
    get_platform_service,
)

__all__ = [
    # Core dependencies
    "SettingsDep",
    "IdentityServiceDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "GoogleWorkspaceClientsDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
    "NotificationServiceDep",
    "CommandServiceDep",
    "PersistenceServiceDep",
    "PlatformServiceDep",
    # Core providers
    "get_settings",
    "get_identity_service",
    "get_jwks_manager",
    "get_aws_clients",
    "get_google_workspace_clients",
    "get_event_dispatcher",
    "get_translation_service",
    "get_idempotency_service",
    "get_resilience_service",
    "get_notification_service",
    "get_command_service",
    "get_persistence_service",
    "get_platform_service",
]
