"""Access Sync FastAPI route handlers — HTTP transport layer only.

Defines the POST /api/v1/access/sync-runs and GET /api/v1/access/sync-runs/{job_id}
endpoints.  Handlers validate the incoming request schema, check or acquire the
concurrency lock, delegate execution to ``job_runner``, and map the result to an
HTTP response.  No business logic lives here — all decisions belong in
``policies.py`` and ``coordinator.py``.

FastAPI ``Depends`` factories for the coordinator and settings are declared in
``providers.py``.  Route handlers consume them through type-annotated protocols
so they are test-substitutable without monkey-patching FastAPI.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Protocol, Union

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, Security

from infrastructure.identity.models import User
from infrastructure.services import get_current_user, get_idempotency_service
from packages.access.sync.coordinator import AccessSyncCoordinatorPort
from packages.access.sync.platform_lock import (
    check_lock,
    platform_lock_key,
    user_lock_key,
)
from packages.access.sync.providers import (
    get_access_sync_coordinator,
    get_access_sync_settings,
)
from packages.access.sync.schemas import (
    AccessSyncRequest,
    PlatformSyncJobAcceptedResponse,
    SyncJobStatusResponse,
    UserSyncJobAcceptedResponse,
    UserSyncRequest,
)
from packages.access.sync.job_runner import (
    spawn_platform_sync_thread,
    spawn_user_sync_thread,
)
from packages.access.sync.presenters import to_http_status_response

logger = structlog.get_logger()
router = APIRouter(prefix="/access", tags=["Access Management"])


# ---------------------------------------------------------------------------
# Settings protocol
# ---------------------------------------------------------------------------


class _AccessSyncSettingsPort(Protocol):
    """Structural contract for the settings object consumed by route handlers."""

    enabled: bool
    job_ttl_seconds: int
    lock_stale_seconds: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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
    job_ttl = settings.job_ttl_seconds
    lock_stale = settings.lock_stale_seconds

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
        spawn_user_sync_thread(
            coordinator=coordinator,
            idempotency=idempotency,
            job_id=job_id,
            user_email=str(request.user_email),
            platform=request.platform,
            dry_run=request.dry_run,
            request_id=correlation_id,
            started_at=started_at,
            job_ttl_seconds=job_ttl,
        )
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
    spawn_platform_sync_thread(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id=job_id,
        platform=request.platform,
        dry_run=request.dry_run,
        request_id=correlation_id,
        started_at=started_at,
        job_ttl_seconds=job_ttl,
    )
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
    return to_http_status_response(record)
