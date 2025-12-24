"""
Dependency injection services.

Provides type aliases and provider functions for FastAPI dependency injection.
"""

from infrastructure.services.dependencies import (
    SettingsDep,
    IdentityResolverDep,
    JWKSManagerDep,
    AWSClientsDep,
)
from infrastructure.services.providers import (
    get_settings,
    get_identity_resolver,
    get_jwks_manager,
    get_aws_clients,
)

__all__ = [
    "SettingsDep",
    "IdentityResolverDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "get_settings",
    "get_identity_resolver",
    "get_jwks_manager",
    "get_aws_clients",
]
