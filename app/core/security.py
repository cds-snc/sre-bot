"""JWT security and JWKS management.

DEPRECATED: This module is maintained for backward compatibility with legacy feature
modules (incident, roles, aws, opsgenie, trello, atip, etc.). New code should import
from infrastructure.security instead.

Migration:
    from core.security import validate_jwt_token, jwks_manager  # OLD
    from infrastructure.security import validate_jwt_token, JWKSManager  # NEW
"""

import warnings
from typing import Any, Dict, Optional, Tuple
import structlog

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWTError, PyJWKClientError, decode

from core.config import settings


# Issue deprecation warning on import
warnings.warn(
    "core.security is deprecated, use infrastructure.security instead",
    DeprecationWarning,
    stacklevel=2,
)


ISSUER_CONFIG = settings.server.ISSUER_CONFIG

logger = structlog.get_logger()

security = HTTPBearer()


class JWKSManager:
    """
    A class to manage JWKS clients for different issuers.
    It initializes a JWKS client for each issuer in the provided configuration.
    Attributes:
        issuer_config (Dict[str, Dict[str, Any]]): A dictionary containing issuer configurations.
        jwks_clients (Dict[str, PyJWKClient]): A dictionary to store JWKS clients for each issuer.
    """

    def __init__(self, issuer_config: Optional[Dict[str, Dict[str, Any]]]):
        self.issuer_config = issuer_config
        self.jwks_clients: Dict[str, PyJWKClient] = {}

    def get_jwks_client(self, issuer: str) -> Optional[PyJWKClient]:
        """Get the JWKS client for the specified issuer.

        Args:
            issuer (str): The issuer for which to get the JWKS client.
        Returns:
            Optional[PyJWKClient]: The JWKS client for the specified issuer, or None if not found.
        """
        if not self.issuer_config or issuer not in self.issuer_config:
            return None
        if issuer not in self.jwks_clients:
            log = logger.bind(issuer=issuer)
            try:
                cfg = self.issuer_config[issuer]
                self.jwks_clients[issuer] = PyJWKClient(
                    cfg["jwks_uri"], cache_jwk_set=True, lifespan=3600, timeout=10
                )
            except Exception as e:
                log.warning("jwks_client_initialization_failed", error=str(e))
                return None
        return self.jwks_clients[issuer]


jwks_manager = JWKSManager(getattr(settings.server, "ISSUER_CONFIG", None))


def get_issuer_from_token(token: str) -> Optional[str]:
    """
    Extract the issuer from the JWT token without verifying the signature.
    Args:
        token (str): The JWT token.
    Returns:
        str | None: The issuer (iss) claim from the token if present, otherwise None.
    """
    try:
        unverified_payload = decode(token, options={"verify_signature": False})
        return unverified_payload.get("iss")
    except Exception:
        return None


def extract_user_info_from_token(token: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract user ID and email from the JWT token without verifying the signature.
    Args:
        token (str): The JWT token.
    Returns:
        Tuple[str, str] | Tuple[None, None]: A tuple containing the user ID and email if present,
        otherwise (None, None).
    """
    payload: Dict[str, Any] | None = None
    try:
        payload = decode(token, options={"verify_signature": False})
        user_id = None
        user_email = None

        if "email" in payload:
            user_email = payload["email"]

        if "sub" in payload:
            user_id = payload["sub"].split("/")[-1]

        return user_id, user_email
    except Exception as e:
        logger.warning("user_info_extraction_failed", error=str(e))
        return None, None


async def validate_jwt_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Dict[str, Any]:
    """
    Validate the JWT token and extract user information.
    Args:
        credentials (HTTPAuthorizationCredentials): The HTTP authorization credentials containing the JWT token.
    Returns:
        Dict[str, Any]: The decoded payload of the JWT token.
    Raises:
        HTTPException: If the token is invalid, untrusted, or if any other error occurs during validation.
    """
    if (
        credentials is None
        or not credentials.scheme == "Bearer"
        or not credentials.credentials
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = credentials.credentials
    issuer = get_issuer_from_token(token)
    if not issuer:
        raise HTTPException(status_code=401, detail="Issuer not found in token")
    jwks_client = jwks_manager.get_jwks_client(issuer)
    if not jwks_client or not jwks_manager.issuer_config:
        raise HTTPException(status_code=401, detail="Untrusted or missing token issuer")
    cfg = jwks_manager.issuer_config[issuer]
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = decode(
            token,
            signing_key.key,
            algorithms=cfg["algorithms"],
            audience=cfg["audience"],
            options={"verify_exp": True},
        )
        return payload
    except (PyJWKClientError, PyJWTError) as e:
        logger.warning("jwt_validation_failed", error=str(e), issuer=issuer)
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}") from e
