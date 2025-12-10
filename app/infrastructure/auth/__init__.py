"""Infrastructure auth module - authentication and authorization.

Exports:
    identity_resolver: Global identity resolver instance
    UserIdentity: Normalized user identity dataclass
    IdentitySource: Enum of identity sources
    validate_jwt_token: JWT token validation function
    jwks_manager: Global JWKS manager instance
"""

from infrastructure.auth.identity import (
    identity_resolver,
    UserIdentity,
    IdentitySource,
    IdentityResolver,
)
from infrastructure.auth.security import (
    validate_jwt_token,
    jwks_manager,
    JWKSManager,
    get_issuer_from_token,
    extract_user_info_from_token,
)

__all__ = [
    "identity_resolver",
    "UserIdentity",
    "IdentitySource",
    "IdentityResolver",
    "validate_jwt_token",
    "jwks_manager",
    "JWKSManager",
    "get_issuer_from_token",
    "extract_user_info_from_token",
]
