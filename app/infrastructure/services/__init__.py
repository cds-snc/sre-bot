"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import SettingsDep, LoggerDep
from infrastructure.services.providers import get_settings, get_logger

__all__ = [
    "SettingsDep",
    "LoggerDep",
    "get_settings",
    "get_logger",
]
