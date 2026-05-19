"""Infrastructure security and authentication services.

This module provides JWT token validation, JWKS management, and related
security utilities for API authentication.

Exports:
    JWKSManager: Manages JWKS clients for different issuers
    get_issuer_from_token: Extract issuer from JWT token
    extract_user_info_from_token: Extract user info from JWT token
    validate_jwt_token: Validate JWT token and extract payload
    get_current_user: FastAPI Security() dependency — validates JWT and returns User
"""

from infrastructure.security.jwks import JWKSManager, get_jwks_manager
from infrastructure.security.jwt import (
    extract_user_info_from_token,
    get_issuer_from_token,
    validate_jwt_token,
)
from infrastructure.security.current_user import get_current_user
from infrastructure.security.rate_limiter import get_limiter, setup_rate_limiter

__all__ = [
    "JWKSManager",
    "get_jwks_manager",
    "get_issuer_from_token",
    "extract_user_info_from_token",
    "validate_jwt_token",
    "get_current_user",
    "get_limiter",
    "setup_rate_limiter",
]
