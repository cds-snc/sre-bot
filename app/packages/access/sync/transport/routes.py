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

from infrastructure.services import get_current_user, get_idempotency_service
from packages.access.sync.coordinator import AccessSyncCoordinatorPort
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access.sync.domain import ReconciliationOutcome, SyncOutcome
from packages.access.sync.platform_lock import (
    acquire_lock,
    check_lock,
    platform_lock_key,
    release_lock,
    user_lock_key,
)

from packages.access.sync.schemas import (
    AccessSyncRequest,
    PlatformSyncJobAcceptedResponse,
    SyncJobStatusResponse,
    UserSyncJobAcceptedResponse,
    UserSyncRequest,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/access", tags=["Access Management"])


def _run_user_sync_job(
    coordinator: AccessSyncCoordinatorPort,
    idempotency: IdempotencyService,
    job_id: str,
    user_email: str,
    platform: str,
    dry_run: bool,
    request_id: str,
    started_at: str,
    job_ttl_seconds: int,
) -> None:
    """Background thread target: run user sync and persist the outcome."""
    log = logger.bind(
        job_id=job_id, user_email=user_email, platform=platform, dry_run=dry_run
    )
    payload: dict[str, Any]
    log.info("user_sync_job_started", correlation_id=request_id)
    try:
        result = coordinator.sync_user(
            user_email=user_email,
            platform=platform,
            dry_run=dry_run,
            request_id=request_id,
        )
        completed_at = datetime.now(timezone.utc).isoformat()
        if result.is_success and result.data is not None:
            outcome: SyncOutcome = result.data  # type: ignore[assignment]
            payload = {
                "job_id": job_id,
                "sync_type": "user",
                "user_email": user_email,
                "platform": platform,
                "dry_run": dry_run,
                "status": "completed",
                "started_at": started_at,
                "completed_at": completed_at,
                "actions_planned": outcome.planned_actions,
                "actions_applied": outcome.applied_actions,
                "requires_manual_action": outcome.requires_manual_action,
            }
            log.info(
                "user_sync_job_completed",
                applied=len(outcome.applied_actions),
                dry_run=dry_run,
            )
        else:
            payload = {
                "job_id": job_id,
                "sync_type": "user",
                "user_email": user_email,
                "platform": platform,
                "dry_run": dry_run,
                "status": "failed",
                "started_at": started_at,
                "completed_at": completed_at,
                "error": result.message or "sync_failed",
            }
            log.warning(
                "user_sync_job_failed",
                error=result.message,
                error_code=result.error_code,
            )
    except Exception as exc:
        completed_at = datetime.now(timezone.utc).isoformat()
        payload = {
            "job_id": job_id,
            "sync_type": "user",
            "user_email": user_email,
            "platform": platform,
            "dry_run": dry_run,
            "status": "failed",
            "started_at": started_at,
            "completed_at": completed_at,
            "error": "sync_failed",
        }
        log.error("user_sync_job_error", error=str(exc), error_type=type(exc).__name__)
    idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)
    release_lock(
        user_lock_key(platform, user_email), payload, idempotency, job_ttl_seconds
    )


def _run_platform_sync_job(
    coordinator: AccessSyncCoordinatorPort,
    idempotency: IdempotencyService,
    job_id: str,
    platform: str,
    dry_run: bool,
    request_id: str,
    started_at: str,
    job_ttl_seconds: int,
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
        ttl_seconds=job_ttl_seconds,
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
            "error": "sync_failed",
        }
        log.error(
            "platform_sync_job_error",
            error=str(exc),
            error_type=type(exc).__name__,
        )
    idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)
    release_lock(platform_lock_key(platform), payload, idempotency, job_ttl_seconds)


class _AccessSyncSettingsPort(Protocol):
    """Structural contract for the settings object consumed by route handlers."""

    enabled: bool
    sync_job_ttl_seconds: int
    sync_lock_stale_after_seconds: int


@router.post(
    "/sync-runs",
    response_model=Union[UserSyncJobAcceptedResponse, PlatformSyncJobAcceptedResponse],
    summary="Sync access",
    description=(
        "Converge user or platform access state to match IDP group membership policy. "
        "Use sync_type='user' for on-demand single-user sync (triggered by events, "
        "webhooks, or API calls); returns 202 with a job_id. "
        "Use sync_type='platform' to enqueue a full batch "
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
) -> Union[UserSyncJobAcceptedResponse, PlatformSyncJobAcceptedResponse]:
    """Enqueue an on-demand user sync or a full platform sync job."""
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

    idempotency = get_idempotency_service()
    job_ttl = settings.sync_job_ttl_seconds
    lock_stale = settings.sync_lock_stale_after_seconds

    if isinstance(request, UserSyncRequest):
        lock_key = user_lock_key(request.platform, str(request.user_email))
        running = check_lock(lock_key, idempotency, lock_stale)
        if running is not None:
            log.info("user_sync_already_running", existing_job_id=running.get("job_id"))
            response.status_code = 202
            return UserSyncJobAcceptedResponse(
                success=True,
                job_id=running["job_id"],
                platform=request.platform,
                user_email=str(request.user_email),
                dry_run=running.get("dry_run", request.dry_run),
                status="in_progress",
                started_at=running.get("started_at", ""),
            )

        job_id = str(uuid.uuid4())
        correlation_id = request.request_id or job_id
        started_at = datetime.now(timezone.utc).isoformat()
        acquire_lock(
            lock_key,
            {
                "job_id": job_id,
                "sync_type": "user",
                "user_email": str(request.user_email),
                "platform": request.platform,
                "dry_run": request.dry_run,
                "status": "running",
                "started_at": started_at,
            },
            idempotency,
            job_ttl,
        )
        idempotency.set(
            job_id,
            {
                "job_id": job_id,
                "sync_type": "user",
                "user_email": str(request.user_email),
                "platform": request.platform,
                "dry_run": request.dry_run,
                "status": "in_progress",
                "started_at": started_at,
            },
            ttl_seconds=job_ttl,
        )
        thread = threading.Thread(
            target=_run_user_sync_job,
            kwargs={
                "coordinator": coordinator,
                "idempotency": idempotency,
                "job_id": job_id,
                "user_email": str(request.user_email),
                "platform": request.platform,
                "dry_run": request.dry_run,
                "request_id": correlation_id,
                "started_at": started_at,
                "job_ttl_seconds": job_ttl,
            },
            daemon=True,
            name=f"user-sync-{job_id[:8]}",
        )
        thread.start()
        log.info("user_sync_job_enqueued", job_id=job_id, correlation_id=correlation_id)
        response.status_code = 202
        return UserSyncJobAcceptedResponse(
            success=True,
            job_id=job_id,
            platform=request.platform,
            user_email=str(request.user_email),
            dry_run=request.dry_run,
            status="in_progress",
            started_at=started_at,
        )

    # Platform sync
    running = check_lock(platform_lock_key(request.platform), idempotency, lock_stale)
    if running is not None:
        log.info(
            "platform_sync_already_running",
            existing_job_id=running.get("job_id"),
        )
        response.status_code = 202
        return PlatformSyncJobAcceptedResponse(
            success=True,
            job_id=running["job_id"],
            platform=request.platform,
            dry_run=running.get("dry_run", request.dry_run),
            status="in_progress",
            started_at=running.get("started_at", ""),
        )

    job_id = str(uuid.uuid4())
    correlation_id = request.request_id or job_id
    started_at = datetime.now(timezone.utc).isoformat()
    acquire_lock(
        platform_lock_key(request.platform),
        {
            "job_id": job_id,
            "platform": request.platform,
            "dry_run": request.dry_run,
            "status": "running",
            "started_at": started_at,
        },
        idempotency,
        job_ttl,
    )
    idempotency.set(
        job_id,
        {
            "job_id": job_id,
            "platform": request.platform,
            "dry_run": request.dry_run,
            "status": "in_progress",
            "started_at": started_at,
        },
        ttl_seconds=job_ttl,
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
            "job_ttl_seconds": job_ttl,
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


@router.get(
    "/sync-runs/{job_id}",
    response_model=SyncJobStatusResponse,
    summary="Get sync job status",
    description=(
        "Poll the status of an enqueued sync job (user or platform). "
        "Returns the current state (in_progress, completed, or failed) "
        "and, once finished, the sync outcome. "
        "Records expire after 24 hours."
    ),
)
def get_sync_job_status(
    job_id: str,
    current_user: Annotated[
        User, Security(get_current_user, scopes=["sre-bot:access-sync"])
    ],
) -> SyncJobStatusResponse:
    """Return the current status and outcome of a sync job."""
    idempotency = get_idempotency_service()
    record = idempotency.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Sync job not found or has expired")
    return SyncJobStatusResponse(**record)
