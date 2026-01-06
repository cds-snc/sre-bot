"""JWT token validation and claims extraction.

This module provides JWT token validation with issuer verification
and user information extraction from token claims.
"""

from typing import Any, Dict, Optional, Tuple

import structlog
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError, decode

from infrastructure.security.jwks import JWKSManager

logger = structlog.get_logger()
security = HTTPBearer()


def get_issuer_from_token(token: str) -> Optional[str]:
    """Extract issuer from JWT token without verifying signature.

    Args:
        token: The JWT token

    Returns:
        The issuer (iss) claim from the token, or None if not present
    """
    try:
        unverified_payload = decode(token, options={"verify_signature": False})
        return unverified_payload.get("iss")
    except Exception as e:
        log = logger.bind(error=str(e))
        log.debug("issuer_extraction_failed")
        return None


def extract_user_info_from_token(token: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract user ID and email from JWT token without verifying signature.

    Args:
        token: The JWT token

    Returns:
        Tuple of (user_id, email). Either or both may be None if not in token.
    """
    try:
        payload = decode(token, options={"verify_signature": False})
        user_id = None
        user_email = None

        # Extract email if present
        if "email" in payload:
            user_email = payload["email"]

        # Extract user ID from 'sub' claim (subject is always present)
        if "sub" in payload:
            # sub may be in format "issuer/user_id", extract the last part
            user_id = payload["sub"].split("/")[-1]

        return user_id, user_email
    except Exception as e:
        log = logger.bind(error=str(e))
        log.debug("user_info_extraction_failed")
        return None, None


def validate_jwt_token(
    jwks_manager: JWKSManager,
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """Validate JWT token and extract payload.

    Args:
        credentials: HTTP authorization credentials containing JWT token
        jwks_manager: JWKS manager instance

    Returns:
        The decoded and verified JWT payload

    Raises:
        HTTPException: 401 if token is invalid, untrusted, or missing
    """
    if not jwks_manager:
        raise HTTPException(status_code=500, detail="JWKS manager not configured")

    # Validate credentials structure
    if (
        credentials is None
        or not credentials.scheme == "Bearer"
        or not credentials.credentials
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = credentials.credentials

    # Extract issuer from token
    issuer = get_issuer_from_token(token)
    if not issuer:
        raise HTTPException(status_code=401, detail="Issuer not found in token")

    # Get JWKS client for issuer
    jwks_client = jwks_manager.get_jwks_client(issuer)
    if not jwks_client or not jwks_manager.issuer_config:
        log = logger.bind(issuer=issuer)
        log.warning("untrusted_or_missing_issuer")
        raise HTTPException(status_code=401, detail="Untrusted or missing token issuer")

    # Get issuer configuration
    cfg = jwks_manager.issuer_config.get(issuer)
    if not cfg:
        raise HTTPException(status_code=401, detail="Invalid token issuer")

    # Verify and decode token
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = decode(
            token,
            signing_key.key,
            algorithms=cfg.get("algorithms", ["RS256"]),
            audience=cfg.get("audience"),
            options={"verify_exp": True},
        )
        log = logger.bind(issuer=issuer)
        log.info("jwt_validation_successful")
        return payload
    except (PyJWTError, Exception) as e:
        log = logger.bind(issuer=issuer, error=str(e))
        log.warning("jwt_validation_failed")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}") from e
