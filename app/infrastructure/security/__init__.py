"""Infrastructure security and authentication services.

This module provides JWT token validation, JWKS management, and related
security utilities for API authentication.

Exports:
    JWKSManager: Manages JWKS clients for different issuers
    get_issuer_from_token: Extract issuer from JWT token
    extract_user_info_from_token: Extract user info from JWT token
    validate_jwt_token: Validate JWT token and extract payload
"""

from infrastructure.security.jwks import JWKSManager
from infrastructure.security.jwt import (
    extract_user_info_from_token,
    get_issuer_from_token,
    validate_jwt_token,
)

__all__ = [
    "JWKSManager",
    "get_issuer_from_token",
    "extract_user_info_from_token",
    "validate_jwt_token",
]
