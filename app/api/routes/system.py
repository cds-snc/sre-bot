from fastapi import APIRouter
from core.config import settings

router = APIRouter(tags=["System"])


# Route53 uses this as a healthcheck every 30 seconds and the alb uses this as a checkpoint every 10 seconds.
# As a result, we are giving a generous rate limit of so that we don't run into any issues with the healthchecks
# @limiter.limit("50/minute")
@router.get("/version")
def get_version():
    """Get the version of the application."""
    return {"version": settings.GIT_SHA}


@router.get("/health")
def get_health():
    """Healthcheck endpoint."""
    return {"status": "ok"}
