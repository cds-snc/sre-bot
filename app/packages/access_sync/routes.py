"""Access Sync FastAPI route handlers.

Thin handlers: validate input, call service, map result to HTTP response.
No business logic lives here.
"""

import structlog
from fastapi import APIRouter, HTTPException

from infrastructure.operations import OperationStatus
from infrastructure.services import SettingsDep
from packages.access_sync.providers import (
    get_access_sync_registry,
    get_access_sync_service,
)
from packages.access_sync.schemas import (
    AccessSyncRequest,
    AccessSyncResponse,
    SyncStatusResponse,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/access-sync", tags=["access-sync"])


@router.post(
    "/sync",
    response_model=AccessSyncResponse,
    summary="Sync user access",
    description=(
        "Converge a single user's authentication and entitlement state on the "
        "target platform to match IDP group membership policy."
    ),
)
def sync_user_endpoint(
    request: AccessSyncRequest,
    settings: SettingsDep,
) -> AccessSyncResponse:
    """Trigger an on-demand sync for one user on one platform."""
    log = logger.bind(
        user_email=request.user_email,
        platform=request.platform,
        dry_run=request.dry_run,
        endpoint="POST /access-sync/sync",
    )
    log.info("sync_user_request")

    service = get_access_sync_service()
    result = service.sync_user(
        user_email=request.user_email,
        platform=request.platform,
        dry_run=request.dry_run,
        request_id=request.request_id or "",
    )

    if result.is_success:
        actions = result.data if result.data is not None else []
        return AccessSyncResponse(
            success=True,
            message=result.message,
            platform=request.platform,
            user_email=request.user_email,
            dry_run=request.dry_run,
            actions_applied=actions,
        )

    if result.status == OperationStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail=result.message)
    if result.status == OperationStatus.PERMANENT_ERROR:
        raise HTTPException(status_code=400, detail=result.message)

    raise HTTPException(status_code=500, detail=result.message)


@router.get(
    "/status",
    response_model=SyncStatusResponse,
    summary="Access Sync status",
    description="Return the list of registered platform adapters.",
)
def get_status_endpoint(
    settings: SettingsDep,
) -> SyncStatusResponse:
    """Return service health and registered platforms."""
    registry = get_access_sync_registry()
    return SyncStatusResponse(
        healthy=True,
        registered_platforms=registry.registered_platforms(),
    )
