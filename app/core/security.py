from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import PyJWKClient, PyJWTError, PyJWKClientError, decode

from core.config import settings
from core.logging import get_module_logger


ISSUER_CONFIG = settings.server.ISSUER_CONFIG

logger = get_module_logger()
security = HTTPBearer()

logger.info("issuer_config_loaded", issuer_config=ISSUER_CONFIG)


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
        logger.info(
            "get_jwks_client_called", issuer=issuer, issuer_config=self.issuer_config
        )
        if not self.issuer_config or issuer not in self.issuer_config:
            return None
        if issuer not in self.jwks_clients:
            try:
                cfg = self.issuer_config[issuer]
                logger.info("creating_jwks_client", jwks_uri=cfg.get("jwks_uri"))
                self.jwks_clients[issuer] = PyJWKClient(
                    cfg["jwks_uri"], cache_jwk_set=True, lifespan=3600, timeout=10
                )
            except Exception as e:
                logger.warning(
                    "jwks_client_initialization_failed", error=str(e), issuer=issuer
                )
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

    logger.info("get_issuer_from_token", token=token)
    try:
        unverified_payload = decode(token, options={"verify_signature": False})
        logger.info(
            "unverified_payload",
            unverified_payload=unverified_payload,
        )
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
    try:
        payload = decode(token, options={"verify_signature": False})
        user_id = None
        user_email = None

        # For user JWTs, email may be a top-level claim
        if "email" in payload:
            user_email = payload["email"]

        # sub is always present
        if "sub" in payload:
            user_id = payload["sub"].split("/")[-1]
        logger.info("user_info_extracted", user_id=user_id, user_email=user_email)

        return user_id, user_email
    except Exception as e:
        logger.warning(
            "user_info_extraction_failed",
            error=str(e),
            payload=payload,
        )
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
    logger.info(
        "validate_jwt_token",
        credentials=credentials,
    )
    if (
        credentials is None
        or not credentials.scheme == "Bearer"
        or not credentials.credentials
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    token = credentials.credentials
    logger.info("token_received", token=token)
    issuer = get_issuer_from_token(token)
    logger.info("issuer_extracted", issuer=issuer)
    if not issuer:
        raise HTTPException(status_code=401, detail="Issuer not found in token")
    jwks_client = jwks_manager.get_jwks_client(issuer)
    logger.info("jwks_client_result", jwks_client=bool(jwks_client))
    if not jwks_client or not jwks_manager.issuer_config:
        raise HTTPException(status_code=401, detail="Untrusted or missing token issuer")
    cfg = jwks_manager.issuer_config[issuer]
    logger.info("jwks_config_used", cfg=cfg)
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        logger.info("signing_key_obtained", signing_key=str(signing_key))
        payload = decode(
            token,
            signing_key.key,
            algorithms=cfg["algorithms"],
            audience=cfg["audience"],
            options={"verify_exp": True},
        )
        logger.info("jwt_token_validated", payload=payload)
        return payload
    except (PyJWKClientError, PyJWTError) as e:
        logger.warning("jwt_validation_failed", error=str(e), issuer=issuer)
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}") from e
