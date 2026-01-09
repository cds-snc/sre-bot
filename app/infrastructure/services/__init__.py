"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import (
    SettingsDep,
    IdentityServiceDep,
    JWKSManagerDep,
    AWSClientsDep,
    EventDispatcherDep,
    TranslationServiceDep,
    IdempotencyServiceDep,
    ResilienceServiceDep,
    NotificationServiceDep,
    CommandServiceDep,
    PersistenceServiceDep,
)
from infrastructure.services.providers import (
    get_settings,
    get_identity_service,
    get_jwks_manager,
    get_aws_clients,
    get_event_dispatcher,
    get_translation_service,
    get_idempotency_service,
    get_resilience_service,
    get_notification_service,
    get_command_service,
    get_persistence_service,
)

__all__ = [
    "SettingsDep",
    "IdentityServiceDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
    "NotificationServiceDep",
    "CommandServiceDep",
    "PersistenceServiceDep",
    "get_settings",
    "get_identity_service",
    "get_jwks_manager",
    "get_aws_clients",
    "get_event_dispatcher",
    "get_translation_service",
    "get_idempotency_service",
    "get_resilience_service",
    "get_notification_service",
    "get_command_service",
    "get_persistence_service",
]
