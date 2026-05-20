"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import (
    AppSettingsDep,
    SettingsDep,
)
from infrastructure.services.providers import (
    get_app_settings,
    get_settings,
)

__all__ = [
    # Core dependencies
    "AppSettingsDep",
    "SettingsDep",
    # Core providers
    "get_app_settings",
    "get_settings",
]
