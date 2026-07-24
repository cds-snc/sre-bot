"""Application rate limiter.

Provides the singleton Limiter instance used by route handlers and wired
into the FastAPI app in server/server.py.

App wiring (app.state.limiter and the RateLimitExceeded exception handler) is
done once in server/server.py via setup_rate_limiter().
"""

from functools import lru_cache

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


async def _rate_limit_handler(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(status_code=429, content={"message": "Rate limit exceeded"})
    raise exc  # let FastAPI handle anything unexpected


@lru_cache(maxsize=1)
def get_limiter() -> Limiter:
    """Return the application-scoped rate limiter singleton."""
    return Limiter(key_func=get_remote_address)


def setup_rate_limiter(app: FastAPI) -> None:
    """Wire the rate limiter into a FastAPI application instance.

    Sets app.state.limiter (required by slowapi) and registers the
    RateLimitExceeded exception handler.  Call once during app construction.
    """
    app.state.limiter = get_limiter()
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
