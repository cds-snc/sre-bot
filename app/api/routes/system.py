from fastapi import APIRouter, Request
from core.config import settings
from api.dependencies.rate_limits import get_limiter

router = APIRouter(tags=["System"])
limiter = get_limiter()


# Route53 uses this as a healthcheck every 30 seconds and the alb uses this as a checkpoint every 10 seconds.
# As a result, we are giving a generous rate limit of so that we don't run into any issues with the healthchecks
@router.get("/version")
@limiter.limit("50/minute")
def get_version(request: Request):  # pylint: disable=unused-argument
    """Get the version of the application."""
    return {"version": settings.GIT_SHA}


@router.get("/health")
@limiter.limit("50/minute")
def get_health(request: Request):  # pylint: disable=unused-argument
    """Healthcheck endpoint."""
    return {"status": "ok"}
