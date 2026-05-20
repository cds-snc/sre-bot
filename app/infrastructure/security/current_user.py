"""Authenticated principal resolution for FastAPI routes.

Provides get_current_user() — the single dependency for JWT-protected endpoints.
It validates the Bearer JWT via JWKS, enforces any scopes declared by the route,
and returns a normalized User from the IdentityService.

Usage in route handlers:

    from fastapi import Security
    from typing import Annotated
    from infrastructure.security.models import User
    from infrastructure.security import get_current_user

    # Authentication only (valid JWT required, no scope check):
    @router.get("/me")
    def get_me(current_user: Annotated[User, Security(get_current_user)]) -> dict:
        return {"email": current_user.email}

    # Authentication + named scope:
    @router.post("/access/sync-runs")
    def sync(
        current_user: Annotated[User, Security(get_current_user, scopes=["sre-bot:access-sync"])]
    ) -> dict:
        ...

Development bypass:
    Set DEV_BYPASS_TOKEN=<random-string> in your .env (non-production only).
    Pass that value as the Bearer token to skip JWKS validation entirely.
    A synthetic User is returned. Blocked when PREFIX="" (production).

Slack transport: authentication is handled at the platform layer via Slack signing
secret verification before command handlers are invoked. The CommandPayload.user_id
carries the verified Slack user identity — no JWT dependency needed in Slack handlers.
"""

from typing import Annotated, Any, List, Optional

import structlog
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, SecurityScopes

from infrastructure.security.jwks import JWKSManager
from infrastructure.security.jwt import validate_jwt_token
from infrastructure.security.models import AuthPrincipalSource, User
from infrastructure.configuration.infrastructure.server import (
    get_server_settings,
)
from infrastructure.configuration import get_app_settings
from infrastructure.security import get_jwks_manager

logger = structlog.get_logger()

# auto_error=False so that we return 401 (not 403) for missing Authorization headers.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    security_scopes: SecurityScopes,
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    jwks_manager: Annotated[JWKSManager, Depends(get_jwks_manager)],
) -> User:
    """Validate a JWT Bearer token and return the authenticated principal.

    This function is designed to be used as a FastAPI Security() dependency.
    It performs token validation, scope enforcement, and identity resolution
    in a single, composable step.

    In non-production environments, if DEV_BYPASS_TOKEN is set in ServerSettings
    and the incoming bearer token matches it exactly, JWKS validation is skipped
    and a synthetic developer User is returned. This bypass is inert in production
    (PREFIX="" disables it).

    JWT scope claims are read from either:
    - ``scope`` (space-separated string, RFC 6749 / OAuth 2.0 style)
    - ``scp`` (string array, Microsoft / Okta style)

    Args:
        security_scopes: Scopes required by this endpoint, collected by FastAPI
            from all Security() declarations in the dependency chain.
        credentials: HTTP bearer credentials from the Authorization header.
        jwks_manager: JWKS manager singleton — injected, never constructed here.
    Returns:
        Authenticated User with identity resolved from JWT claims.

    Raises:
        HTTPException: 401 if the token is absent, invalid, or expired.
        HTTPException: 403 if the token lacks one or more required scopes.
    """
    authenticate_value = (
        f'Bearer scope="{security_scopes.scope_str}"'
        if security_scopes.scopes
        else "Bearer"
    )

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": authenticate_value},
        )

    # Non-production static bypass — allows local smoke testing without Backstage.
    server_settings = get_server_settings()
    app_settings = get_app_settings()
    if not app_settings.is_production and server_settings.DEV_BYPASS_TOKEN:
        if credentials.credentials == server_settings.DEV_BYPASS_TOKEN:
            log = logger.bind(bypass="dev_token")
            log.warning("dev_bypass_token_used")
            return User(
                user_id="dev@local",
                email="dev@local",
                display_name="Dev Bypass User",
                source=AuthPrincipalSource.API_JWT,
                platform_id="dev-bypass",
                permissions=list(security_scopes.scopes),
            )

    payload = validate_jwt_token(jwks_manager=jwks_manager, credentials=credentials)

    token_scopes = _extract_token_scopes(payload)
    missing = [s for s in security_scopes.scopes if s not in token_scopes]
    if missing:
        log = logger.bind(
            required_scopes=security_scopes.scopes,
            token_scopes=token_scopes,
        )
        log.warning("insufficient_token_scopes")
        raise HTTPException(
            status_code=403,
            detail="Not authorized: insufficient token scopes",
            headers={"WWW-Authenticate": authenticate_value},
        )

    return _build_user_from_jwt_payload(payload)


def _build_user_from_jwt_payload(payload: dict[str, Any]) -> User:
    """Build a normalized principal from a verified JWT payload."""
    user_id = str(payload.get("sub", "unknown"))
    email = str(payload.get("email", "unknown"))
    display_name = str(payload.get("name", user_id))

    return User(
        user_id=user_id,
        email=email,
        display_name=display_name,
        source=AuthPrincipalSource.API_JWT,
        platform_id=user_id,
        permissions=list(payload.get("permissions", [])),
        metadata={"jwt_iss": payload.get("iss", "")},
    )


def _extract_token_scopes(payload: dict) -> List[str]:
    """Extract scope strings from a verified JWT payload.

    Handles both RFC 6749 space-separated ``scope`` strings and
    array-style ``scp`` claims (Microsoft / Okta convention).

    Args:
        payload: Decoded, verified JWT claims dict.

    Returns:
        Deduplicated list of scope strings present in the token.
    """
    scope_str = payload.get("scope", "")
    scp_list = payload.get("scp", [])
    scopes: set = set()
    if isinstance(scope_str, str):
        scopes.update(s for s in scope_str.split() if s)
    if isinstance(scp_list, list):
        scopes.update(str(s) for s in scp_list if s)
    return list(scopes)
