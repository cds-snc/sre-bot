"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import (
    AppSettingsDep,
    SettingsDep,
    MaxMindClientDep,
    EventDispatcherDep,
    TranslationServiceDep,
)
from infrastructure.services.providers import (
    get_app_settings,
    get_settings,
    get_maxmind_client,
    get_event_dispatcher,
    get_translation_service,
    t,
)

__all__ = [
    # Core dependencies
    "AppSettingsDep",
    "SettingsDep",
    "MaxMindClientDep",
    "EventDispatcherDep",
    "TranslationServiceDep",
    # Core providers
    "get_app_settings",
    "get_settings",
    "get_maxmind_client",
    "get_event_dispatcher",
    "get_translation_service",
    # Translation helper
    "t",
]
