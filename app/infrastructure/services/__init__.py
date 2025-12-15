"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import SettingsDep, IdentityResolverDep
from infrastructure.services.providers import get_settings, get_identity_resolver

__all__ = [
    "SettingsDep",
    "IdentityResolverDep",
    "get_settings",
    "get_identity_resolver",
]
