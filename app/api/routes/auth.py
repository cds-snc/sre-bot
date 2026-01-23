"""Authentication routes for API access.

Note: OAuth-based authentication (login, logout, callback) has been deprecated
in favor of JWT-based authentication via Backstage issuer configuration.
Authentication is now handled at the API endpoint level using validate_jwt_token.
"""

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from core.security import validate_jwt_token
from api.dependencies.rate_limits import get_limiter

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = get_limiter()


# User information route
@router.get("/me")
@limiter.limit("10/minute")
async def get_user_info(
    request: Request, token_data: dict = Depends(validate_jwt_token)
):
    """
    Get current authenticated user information from JWT token.

    Requires a valid JWT token in the Authorization header.

    Returns:
        dict: User information extracted from the JWT token
              (sub, email, name if available)
    """
    return JSONResponse(
        {
            "sub": token_data.get("sub"),
            "email": token_data.get("email"),
            "name": token_data.get("name"),
            "issuer": token_data.get("iss"),
        }
    )
