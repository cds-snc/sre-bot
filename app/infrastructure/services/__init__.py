"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import (
    AppSettingsDep,
    SettingsDep,
    JWKSManagerDep,
    AWSClientsDep,
    GoogleWorkspaceClientsDep,
    MaxMindClientDep,
    EventDispatcherDep,
    TranslationServiceDep,
    IdempotencyServiceDep,
    ResilienceServiceDep,
    StorageServiceDep,
    AuditTrailServiceDep,
    PlatformServiceDep,
    SlackClientDep,
    DirectoryProviderDep,
)
from infrastructure.services.providers import (
    get_app_settings,
    get_settings,
    get_jwks_manager,
    get_aws_clients,
    get_google_workspace_clients,
    get_maxmind_client,
    get_event_dispatcher,
    get_translation_service,
    get_idempotency_service,
    get_resilience_service,
    get_storage_service,
    get_audit_trail_service,
    get_platform_service,
    get_slack_client,
    get_directory_provider,
    get_slack_provider,
    t,
)
from infrastructure.security.rate_limiter import get_limiter, setup_rate_limiter

# Plugin infrastructure
from infrastructure.services.plugins import (
    hookimpl,
    get_plugin_manager,
    discover_and_init_features,
    collect_feature_i18n_resources,
    register_feature_integrations,
)

__all__ = [
    # Core dependencies
    "AppSettingsDep",
    "SettingsDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "GoogleWorkspaceClientsDep",
    "MaxMindClientDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    "IdempotencyServiceDep",
    "ResilienceServiceDep",
    "NotificationServiceDep",
    "StorageServiceDep",
    "AuditTrailServiceDep",
    "PlatformServiceDep",
    # Platform client facades
    "SlackClientDep",
    "DirectoryProviderDep",
    # Core providers
    "get_app_settings",
    "get_settings",
    "get_jwks_manager",
    "get_aws_clients",
    "get_google_workspace_clients",
    "get_maxmind_client",
    "get_event_dispatcher",
    "get_translation_service",
    "get_idempotency_service",
    "get_resilience_service",
    "get_storage_service",
    "get_audit_trail_service",
    "get_platform_service",
    "get_directory_provider",
    # Platform client providers
    "get_slack_client",
    # Platform provider accessors (ergonomic improvement)
    "get_slack_provider",
    # Translation helper
    "t",
    # Security utilities
    "get_limiter",
    "setup_rate_limiter",
    # Plugin infrastructure
    "hookimpl",
    "get_plugin_manager",
    "discover_and_init_features",
    "collect_feature_i18n_resources",
    "register_feature_integrations",
]
