"""Access Sync FastAPI route handlers.

Thin handlers: validate input, call service, map result to HTTP response.
No business logic lives here.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, Protocol

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.coordinator import AccessSyncCoordinatorPort
from packages.access_sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access_sync.domain import ReconciliationOutcome, SyncOutcome
from packages.access_sync.schemas import (
    AccessSyncRequest,
    AccessSyncResponse,
    PlatformSyncResponse,
    UserSyncResponse,
    UserSyncRequest,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/access", tags=["access-sync"])


class _AccessSyncSettingsPort(Protocol):
    """Structural contract for the settings object consumed by route handlers."""

    enabled: bool


@router.post(
    "/sync-runs",
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
    coordinator: Annotated[
        AccessSyncCoordinatorPort, Depends(get_access_sync_coordinator)
    ],
    settings: Annotated[_AccessSyncSettingsPort, Depends(get_access_sync_settings)],
) -> AccessSyncResponse:
    """Trigger an on-demand user sync or a full platform sync."""
    log = logger.bind(
        sync_type=request.sync_type,
        platform=request.platform,
        dry_run=request.dry_run,
        endpoint="POST /api/v1/access/sync-runs",
    )
    log.info("sync_request")

    if not settings.enabled:
        raise HTTPException(status_code=503, detail="Access Sync is not enabled")

    if isinstance(request, UserSyncRequest):
        result = coordinator.sync_user(
            user_email=str(request.user_email),
            platform=request.platform,
            dry_run=request.dry_run,
            request_id=request.request_id or "",
        )
    else:
        result = coordinator.sync_platform(
            platform=request.platform,
            dry_run=request.dry_run,
            request_id=request.request_id or "",
        )

    if result.is_success:
        return _build_response(request, result.data)

    status_code, detail = _to_public_error(result)
    if status_code >= 500:
        log.error(
            "sync_request_failed",
            status=str(result.status),
            error_code=result.error_code,
            error=result.message,
        )
    else:
        log.warning(
            "sync_request_failed",
            status=str(result.status),
            error_code=result.error_code,
            error=result.message,
        )
    raise HTTPException(status_code=status_code, detail=detail)


def _to_public_error(result: OperationResult) -> tuple[int, str]:
    """Map internal OperationResult errors to safe public API responses."""
    if result.error_code == "FEATURE_DISABLED":
        return 503, "Access Sync is not enabled"
    if result.status == OperationStatus.NOT_FOUND:
        return 404, "Requested access sync resource was not found"
    if result.status == OperationStatus.UNAUTHORIZED:
        return 403, "Not authorized to perform this access sync action"
    if result.status == OperationStatus.PERMANENT_ERROR:
        return 400, "Access sync request could not be completed"
    return 500, "Access sync request failed due to an internal error"


def _build_response(
    request: AccessSyncRequest, data: object  # type: ignore[valid-type]
) -> AccessSyncResponse:
    """Map service result data to the correct response model."""
    if isinstance(request, UserSyncRequest):
        outcome: SyncOutcome = data  # type: ignore[assignment]
        return UserSyncResponse(
            success=True,
            platform=request.platform,
            user_email=request.user_email,
            dry_run=request.dry_run,
            actions_planned=outcome.planned_actions if outcome else [],
            actions_applied=outcome.applied_actions if outcome else [],
            requires_manual_action=outcome.requires_manual_action if outcome else False,
        )
    recon: ReconciliationOutcome = data  # type: ignore[assignment]
    return PlatformSyncResponse(
        success=True,
        platform=request.platform,
        dry_run=request.dry_run,
        users_synced=recon.users_synced if recon else 0,
        users_converged=recon.users_converged if recon else 0,
        orphans_found=recon.orphans_found if recon else 0,
        requires_manual_action_count=(
            recon.requires_manual_action_count if recon else 0
        ),
    )
