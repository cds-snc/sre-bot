"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import (
    AppSettingsDep,
    SettingsDep,
    MaxMindClientDep,
    EventDispatcherDep,
)
from infrastructure.services.providers import (
    get_app_settings,
    get_settings,
    get_maxmind_client,
    get_event_dispatcher,
)

__all__ = [
    # Core dependencies
    "AppSettingsDep",
    "SettingsDep",
    "MaxMindClientDep",
    "EventDispatcherDep",
    # Core providers
    "get_app_settings",
    "get_settings",
    "get_maxmind_client",
    "get_event_dispatcher",
]
