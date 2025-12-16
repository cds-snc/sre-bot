"""
Type aliases for FastAPI dependency injection.

Provides annotated type hints for common infrastructure dependencies.
"""

from typing import Annotated
from fastapi import Depends
from infrastructure.clients.aws.protocols import (
    AWSLowLevelClient,
    DynamoDBClientWrapper,
)
from infrastructure.configuration import Settings
from infrastructure.identity import IdentityResolver
from infrastructure.security.jwks import JWKSManager
from infrastructure.services.providers import (
    get_settings,
    get_identity_resolver,
    get_jwks_manager,
    get_aws_client,
    get_dynamodb_client,
)

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Identity resolver dependency
IdentityResolverDep = Annotated[IdentityResolver, Depends(get_identity_resolver)]

# JWKS manager dependency
JWKSManagerDep = Annotated[JWKSManager, Depends(get_jwks_manager)]

# AWS client dependencies
AWSClientDep = Annotated[AWSLowLevelClient, Depends(get_aws_client)]
DynamoDBClientDep = Annotated[DynamoDBClientWrapper, Depends(get_dynamodb_client)]

__all__ = [
    "SettingsDep",
    "IdentityResolverDep",
    "JWKSManagerDep",
    "AWSClientDep",
    "DynamoDBClientDep",
]
