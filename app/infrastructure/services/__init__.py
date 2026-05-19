"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import (
    AppSettingsDep,
    SettingsDep,
    AWSClientsDep,
    GoogleWorkspaceClientsDep,
    MaxMindClientDep,
    EventDispatcherDep,
    TranslationServiceDep,
    IdempotencyServiceDep,
    ResilienceServiceDep,
    StorageServiceDep,
    AuditTrailServiceDep,
    DirectoryProviderDep,
)
from infrastructure.services.providers import (
    get_app_settings,
    get_settings,
    get_aws_clients,
    get_google_workspace_clients,
    get_maxmind_client,
    get_event_dispatcher,
    get_translation_service,
    get_idempotency_service,
    get_resilience_service,
    get_storage_service,
    get_audit_trail_service,
    get_directory_provider,
    t,
)

__all__ = [
    # Core dependencies
    "AppSettingsDep",
    "SettingsDep",
    "AWSClientsDep",
    "GoogleWorkspaceClientsDep",
    "MaxMindClientDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
    "StorageServiceDep",
    "AuditTrailServiceDep",
    "DirectoryProviderDep",
    # Core providers
    "get_app_settings",
    "get_settings",
    "get_aws_clients",
    "get_google_workspace_clients",
    "get_maxmind_client",
    "get_event_dispatcher",
    "get_translation_service",
    "get_idempotency_service",
    "get_resilience_service",
    "get_storage_service",
    "get_audit_trail_service",
    "get_directory_provider",
    # Translation helper
    "t",
]
