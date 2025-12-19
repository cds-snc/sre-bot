"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated
from fastapi import Depends
from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from infrastructure.security.jwks import JWKSManager
from infrastructure.clients.aws import AWSClients
from infrastructure.services.providers import (
    get_settings,
    get_identity_resolver,
    get_jwks_manager,
    get_aws_clients,
)

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Identity resolver dependency
IdentityResolverDep = Annotated[IdentityResolver, Depends(get_identity_resolver)]

# JWKS manager dependency
JWKSManagerDep = Annotated[JWKSManager, Depends(get_jwks_manager)]

# AWS clients facade dependency - provides attribute-based access to all AWS services
# Usage: aws.dynamodb.get_item(...), aws.identitystore.list_users(...), etc.
AWSClientsDep = Annotated[AWSClients, Depends(get_aws_clients)]

__all__ = [
    "SettingsDep",
    "IdentityResolverDep",
    "JWKSManagerDep",
    "AWSClientsDep",
]
