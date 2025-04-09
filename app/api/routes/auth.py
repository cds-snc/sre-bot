from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from starlette.config import Config
from starlette.datastructures import URL
from authlib.integrations.starlette_client import OAuth, OAuthError  # type: ignore
from core.config import settings
from core.logging import get_module_logger
from api.dependencies.rate_limits import get_limiter
from server.utils import create_access_token

logger = get_module_logger()
router = APIRouter(prefix="/auth", tags=["Authentication"])
limiter = get_limiter()

# Set up Google OAuth
GOOGLE_CLIENT_ID = settings.server.GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET = settings.server.GOOGLE_CLIENT_SECRET
FRONTEND_URL = settings.frontend.FRONTEND_URL
if FRONTEND_URL is None:
    raise ValueError("FRONTEND_URL must be set in the configuration")


class ConfigurationError(Exception):
    """Custom exception for configuration errors."""


# OAuth settings
if settings.is_production:
    if GOOGLE_CLIENT_ID is None or GOOGLE_CLIENT_SECRET is None:
        raise ConfigurationError("Missing OAuth credentials in production")
else:
    if GOOGLE_CLIENT_ID is None:
        logger.warning(
            "oauth_credentials_missing", mode="development", using="dummy_values"
        )
        GOOGLE_CLIENT_ID = "dev-client-id"
    if GOOGLE_CLIENT_SECRET is None:
        GOOGLE_CLIENT_SECRET = "dev-client-secret"

config_data = {
    "GOOGLE_CLIENT_ID": GOOGLE_CLIENT_ID,
    "GOOGLE_CLIENT_SECRET": GOOGLE_CLIENT_SECRET,
}
starlette_config = Config(environ=config_data)
oauth = OAuth(starlette_config)
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


# Logout route
@router.get("/logout")
@limiter.limit("5/minute")
async def logout(request: Request):
    """Log out the current user and clear session data."""
    request.session.pop("user", None)
    response = RedirectResponse(url=FRONTEND_URL)
    response.delete_cookie("access_token")
    return response


# Login route
@router.get("/login")
@limiter.limit("5/minute")
async def login(request: Request):
    """Redirect user to Google OAuth login page."""
    # Get the callback URI for after authentication
    redirect_uri = request.url_for("auth")
    # If in production, ensure HTTPS is used
    if settings.is_production:
        if str(redirect_uri).startswith('http:'):
            redirect_uri = URL(str(redirect_uri).replace('http:', 'https:', 1))

    return await oauth.google.authorize_redirect(request, redirect_uri)


# Authentication callback route
@router.get("/callback")
@limiter.limit("5/minute")
async def auth(request: Request):
    """Process OAuth callback and create user session."""
    try:
        access_token = await oauth.google.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f"<h1>OAuth Error</h1><pre>{error.error}</pre>")

    user_data = access_token.get("userinfo")
    if user_data:
        request.session["user"] = dict(user_data)
        jwt_token = create_access_token(data={"sub": user_data["email"]})
        response = RedirectResponse(url=FRONTEND_URL)
        response.set_cookie(
            "access_token",
            jwt_token,
            httponly=True,
            secure=settings.is_production,
            samesite="strict" if settings.is_production else "lax",
        )
        return response

    return RedirectResponse(url=FRONTEND_URL)


# User information route
@router.get("/me")
@limiter.limit("10/minute")
async def user(request: Request):
    """Return information about the currently logged in user."""
    user = request.session.get("user")
    if user:
        return JSONResponse({"name": user.get("given_name")})
    else:
        return JSONResponse({"error": "Not logged in"})
