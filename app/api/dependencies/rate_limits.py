from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
)


async def rate_limit_handler(_request: Request, exc: Exception):
    """Custom rate limit handler that returns a 429 status code and a custom error message."""
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"message": "Rate limit exceeded"},
        )


def sentinel_key_func(request: Request):
    # Check if the 'X-Sentinel-Source' exists and is not empty
    if request.headers.get("X-Sentinel-Source"):
        return None  # Skip rate limiting if the header exists and is not empty
    return get_remote_address(request)


def setup_rate_limiter(app: FastAPI):
    """
    Setup rate limiting for the FastAPI application.
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)


def get_limiter():
    """
    Returns the limiter instance.
    """
    return limiter
