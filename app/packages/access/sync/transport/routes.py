"""Access Sync FastAPI route handlers — HTTP transport layer only.

Defines the single POST /api/v1/access/sync-runs endpoint.  Handlers here
do three things: validate the incoming request schema, delegate to the
coordinator, and map the ``OperationResult`` to an HTTP response.  No
business logic — all decisions belong in ``policies.py`` and
``coordinator.py``.

FastAPI ``Depends`` factories for the coordinator and settings are declared
in ``providers.py``.  Route handlers consume them through type-annotated
protocols so they are test-substitutable without monkey-patching FastAPI.
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Protocol, Union

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, Security

from infrastructure.identity.models import User
from infrastructure.idempotency import IdempotencyService
from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.services import get_current_user, get_idempotency_service
from packages.access.sync.coordinator import AccessSyncCoordinatorPort
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access.sync.domain import ReconciliationOutcome, SyncOutcome
from packages.access.sync.schemas import (
    AccessSyncRequest,
    PlatformSyncJobAcceptedResponse,
    PlatformSyncJobStatusResponse,
    UserSyncResponse,
    UserSyncRequest,
)

# How long a completed / failed platform sync job record is kept in the cache.
_PLATFORM_SYNC_JOB_TTL_SECONDS = 86400  # 24 h

logger = structlog.get_logger()
router = APIRouter(prefix="/access", tags=["Access Management"])


def _run_platform_sync_job(
    coordinator: AccessSyncCoordinatorPort,
    idempotency: IdempotencyService,
    job_id: str,
    platform: str,
    dry_run: bool,
    request_id: str,
    started_at: str,
) -> None:
    """Background thread target: run platform sync and persist the outcome."""
    log = logger.bind(job_id=job_id, platform=platform, dry_run=dry_run)
    payload: dict[str, Any]
    log.info(
        "platform_sync_job_started",
        correlation_id=request_id,
        poll_path=f"/api/v1/access/sync-runs/{job_id}",
    )
    idempotency.set(
        job_id,
        {
            "job_id": job_id,
            "platform": platform,
            "dry_run": dry_run,
            "status": "running",
            "phase": "syncing",
            "started_at": started_at,
        },
        ttl_seconds=_PLATFORM_SYNC_JOB_TTL_SECONDS,
    )
    try:
        result = coordinator.sync_platform(
            platform=platform,
            dry_run=dry_run,
            request_id=request_id,
        )
        completed_at = datetime.now(timezone.utc).isoformat()
        if result.is_success:
            recon: ReconciliationOutcome = result.data  # type: ignore[assignment]
            payload = {
                "job_id": job_id,
                "platform": platform,
                "dry_run": dry_run,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "users_synced": recon.users_synced if recon else 0,
                "users_converged": recon.users_converged if recon else 0,
                "orphans_found": recon.orphans_found if recon else 0,
                "requires_manual_action_count": (
                    recon.requires_manual_action_count if recon else 0
                ),
            }
            log.info(
                "platform_sync_job_completed",
                users_synced=payload["users_synced"],
                users_converged=payload["users_converged"],
                orphans_found=payload["orphans_found"],
                requires_manual_action_count=payload["requires_manual_action_count"],
                dry_run=dry_run,
            )
        else:
            payload = {
                "job_id": job_id,
                "platform": platform,
                "dry_run": dry_run,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "error": result.message or "sync_failed",
            }
            log.warning(
                "platform_sync_job_failed",
                error=result.message,
                error_code=result.error_code,
            )
    except Exception as exc:
        completed_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "job_id": job_id,
            "platform": platform,
            "dry_run": dry_run,
            "status": "failed",
            "started_at": started_at,
            "completed_at": completed_at,
            "error": str(exc),
        }
        log.error(
            "platform_sync_job_error",
            error=str(exc),
            error_type=type(exc).__name__,
        )
    idempotency.set(job_id, payload, ttl_seconds=_PLATFORM_SYNC_JOB_TTL_SECONDS)


class _AccessSyncSettingsPort(Protocol):
    """Structural contract for the settings object consumed by route handlers."""

    enabled: bool


@router.post(
    "/sync-runs",
    response_model=Union[UserSyncResponse, PlatformSyncJobAcceptedResponse],
    summary="Sync access",
    description=(
        "Converge user or platform access state to match IDP group membership policy. "
        "Use sync_type='user' for on-demand single-user sync (triggered by events, "
        "webhooks, or API calls). Use sync_type='platform' to enqueue a full batch "
        "convergence pass across all users on a platform; returns 202 with a job_id "
        "that can be polled via GET /access/sync-runs/{job_id}."
    ),
)
def sync_endpoint(
    request: AccessSyncRequest,
    response: Response,
    coordinator: Annotated[
        AccessSyncCoordinatorPort, Depends(get_access_sync_coordinator)
    ],
    settings: Annotated[_AccessSyncSettingsPort, Depends(get_access_sync_settings)],
    current_user: Annotated[
        User, Security(get_current_user, scopes=["sre-bot:access-sync"])
    ],
) -> Union[UserSyncResponse, PlatformSyncJobAcceptedResponse]:
    """Trigger an on-demand user sync or a full platform sync."""
    log = logger.bind(
        sync_type=request.sync_type,
        platform=request.platform,
        dry_run=request.dry_run,
        requested_by=current_user.email,
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

        if result.is_success:
            return _build_user_response(request, result.data)

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

    # Platform sync — enqueue as a background job and return 202 immediately.
    # job_id is always server-generated so the caller has a stable polling key.
    # The caller's request_id (if any) is forwarded as a tracing correlation ID only.
    job_id = str(uuid.uuid4())
    correlation_id = request.request_id or job_id
    started_at = datetime.now(timezone.utc).isoformat()
    idempotency = get_idempotency_service()
    idempotency.set(
        job_id,
        {
            "job_id": job_id,
            "platform": request.platform,
            "dry_run": request.dry_run,
            "status": "in_progress",
            "started_at": started_at,
        },
        ttl_seconds=_PLATFORM_SYNC_JOB_TTL_SECONDS,
    )
    thread = threading.Thread(
        target=_run_platform_sync_job,
        kwargs={
            "coordinator": coordinator,
            "idempotency": idempotency,
            "job_id": job_id,
            "platform": request.platform,
            "dry_run": request.dry_run,
            "request_id": correlation_id,
            "started_at": started_at,
        },
        daemon=True,
        name=f"platform-sync-{job_id[:8]}",
    )
    thread.start()
    log.info("platform_sync_job_enqueued", job_id=job_id, correlation_id=correlation_id)
    response.status_code = 202
    return PlatformSyncJobAcceptedResponse(
        success=True,
        job_id=job_id,
        platform=request.platform,
        dry_run=request.dry_run,
        status="in_progress",
        started_at=started_at,
    )


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


@router.get(
    "/sync-runs/{job_id}",
    response_model=PlatformSyncJobStatusResponse,
    summary="Get platform sync job status",
    description=(
        "Poll the status of an enqueued platform sync job. "
        "Returns the current state (in_progress, completed, or failed) "
        "and, once finished, the reconciliation outcome. "
        "Records expire after 24 hours."
    ),
)
def get_sync_job_status(
    job_id: str,
    current_user: Annotated[
        User, Security(get_current_user, scopes=["sre-bot:access-sync"])
    ],
) -> PlatformSyncJobStatusResponse:
    """Return the current status and outcome of a platform sync job."""
    idempotency = get_idempotency_service()
    record = idempotency.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Sync job not found or has expired")
    return PlatformSyncJobStatusResponse(**record)


def _build_user_response(
    request: UserSyncRequest, data: object  # type: ignore[valid-type]
) -> UserSyncResponse:
    """Map sync_user result data to the HTTP response model."""
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
