"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import SettingsDep
from infrastructure.services.providers import get_settings

__all__ = [
    "SettingsDep",
    "get_settings",
]
