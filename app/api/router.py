from fastapi import APIRouter, Request, Depends
from api.routes.system import router as system_router
from api.routes.auth import router as auth_router
from api.v1.router import router as v1_router, legacy_router
from core.logging import get_module_logger

logger = get_module_logger()
api_router = APIRouter()


def log_legacy_calls(request: Request):
    """
    Log a warning message indicating that the legacy API is being used.
    This function is intended to be called when the legacy API is accessed.
    """
    logger.warning(
        "legacy_api_endpoint_accessed",
        path=request.url.path,
        method=request.method,
        query_params=str(request.query_params),
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        authorization_present=bool(request.headers.get("authorization")),
    )


api_router.include_router(system_router)
api_router.include_router(auth_router)
api_router.include_router(legacy_router, dependencies=[Depends(log_legacy_calls)])
api_router.include_router(v1_router, prefix="/api/v1")
