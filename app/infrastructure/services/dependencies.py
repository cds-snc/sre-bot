"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from infrastructure.security.jwks import JWKSManager
from infrastructure.clients.aws import AWSClientFactory, AWSHelpers
from infrastructure.services.providers import (
    get_settings,
    get_identity_resolver,
    get_jwks_manager,
    get_aws_client,
    get_aws_helpers,
)

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Identity resolver dependency
IdentityResolverDep = Annotated[IdentityResolver, Depends(get_identity_resolver)]

# JWKS manager dependency
JWKSManagerDep = Annotated[JWKSManager, Depends(get_jwks_manager)]

# AWS client factory dependency - provides access to all AWS service operations
AWSClientDep = Annotated[AWSClientFactory, Depends(get_aws_client)]

# AWS helpers dependency - provides high-level AWS orchestration operations
AWSHelpersDep = Annotated[AWSHelpers, Depends(get_aws_helpers)]

__all__ = [
    "SettingsDep",
    "IdentityResolverDep",
    "JWKSManagerDep",
    "AWSClientDep",
]
