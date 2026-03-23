"""Access Sync FastAPI route handlers.

Thin handlers: validate input, call service, map result to HTTP response.
No business logic lives here.
"""

import structlog
from fastapi import APIRouter, HTTPException

from infrastructure.operations import OperationStatus
from packages.access_sync.models import ReconciliationOutcome, SyncOutcome
from packages.access_sync.providers import (
    get_access_sync_registry,
    get_access_sync_service,
    get_access_sync_settings,
)
from packages.access_sync.schemas import (
    AccessSyncRequest,
    AccessSyncResponse,
    SyncStatusResponse,
    UserSyncRequest,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/access-sync", tags=["access-sync"])


@router.post(
    "/sync",
    response_model=AccessSyncResponse,
    summary="Sync access",
    description=(
        "Converge user or platform access state to match IDP group membership policy. "
        "Use sync_type='user' for on-demand single-user sync (triggered by events, "
        "webhooks, or API calls). Use sync_type='platform' for a full batch "
        "convergence pass across all users on a platform."
    ),
)
def sync_endpoint(
    request: AccessSyncRequest,
) -> AccessSyncResponse:
    """Trigger an on-demand user sync or a full platform sync."""
    settings = get_access_sync_settings()
    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Sync is not enabled")

    log = logger.bind(
        sync_type=request.sync_type,
        platform=request.platform,
        dry_run=request.dry_run,
        endpoint="POST /access-sync/sync",
    )
    log.info("sync_request")

    service = get_access_sync_service()
    result = service.sync(request)

    if result.is_success:
        return _build_response(request, result.data)

    if result.status == OperationStatus.NOT_FOUND:
        raise HTTPException(status_code=404, detail=result.message)
    if result.status == OperationStatus.PERMANENT_ERROR:
        raise HTTPException(status_code=400, detail=result.message)

    raise HTTPException(status_code=500, detail=result.message)


def _build_response(
    request: AccessSyncRequest, data: object  # type: ignore[valid-type]
) -> AccessSyncResponse:
    """Map service result data to the unified AccessSyncResponse."""
    if isinstance(request, UserSyncRequest):
        outcome: SyncOutcome = data  # type: ignore[assignment]
        return AccessSyncResponse(
            success=True,
            sync_type="user",
            platform=request.platform,
            user_email=request.user_email,
            dry_run=request.dry_run,
            actions_applied=outcome.applied_actions if outcome else [],
            requires_manual_action=outcome.requires_manual_action if outcome else False,
        )
    recon: ReconciliationOutcome = data  # type: ignore[assignment]
    return AccessSyncResponse(
        success=True,
        sync_type="platform",
        platform=request.platform,
        dry_run=request.dry_run,
        users_synced=recon.users_synced if recon else 0,
        users_converged=recon.users_converged if recon else 0,
        orphans_found=recon.orphans_found if recon else 0,
        requires_manual_action_count=(
            recon.requires_manual_action_count if recon else 0
        ),
    )


@router.get(
    "/status",
    response_model=SyncStatusResponse,
    summary="Access Sync status",
    description="Return the list of registered platform adapters.",
)
def get_status_endpoint() -> SyncStatusResponse:
    """Return service health and registered platforms."""
    registry = get_access_sync_registry()
    return SyncStatusResponse(
        healthy=True,
        registered_platforms=registry.registered_platforms(),
    )
