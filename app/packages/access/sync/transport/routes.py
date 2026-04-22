"""Access Sync FastAPI route handlers — HTTP transport layer only.

Defines the POST /api/v1/access/sync-runs and GET /api/v1/access/sync-runs/{job_id}
endpoints.  Handlers validate the incoming request schema, delegate admission
to ``transport.ingress``, and map the result to an HTTP response.  No business
logic lives here — all decisions belong in ``policies.py`` and ``coordinator.py``.

FastAPI ``Depends`` factories for the coordinator and settings are declared in
``providers.py``.  Route handlers consume them through type-annotated protocols
so they are test-substitutable without monkey-patching FastAPI.
"""

from typing import Annotated, Protocol, Union

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, Security

from infrastructure.identity.models import User
from infrastructure.services import get_current_user, get_idempotency_service
from packages.access.sync.application import AccessSyncCoordinatorPort
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
from packages.access.sync.transport.ingress import (
    EnqueuedJob,
    enqueue_platform_sync,
    enqueue_user_sync,
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
# Helpers
# ---------------------------------------------------------------------------


def _http_error_from_enqueue(error_code: str, message: str) -> HTTPException:
    """Map ingress error codes to HTTP exceptions."""
    if error_code == "FEATURE_DISABLED":
        return HTTPException(status_code=503, detail=message)
    return HTTPException(status_code=500, detail=message)


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

    idempotency = get_idempotency_service()

    if isinstance(request, UserSyncRequest):
        result = enqueue_user_sync(
            coordinator=coordinator,
            idempotency=idempotency,
            settings=settings,
            user_email=str(request.user_email),
            platform=request.platform,
            dry_run=request.dry_run,
            request_id=request.request_id or "",
        )
        if not result.is_success or result.data is None:
            raise _http_error_from_enqueue(
                result.error_code or "", result.message or ""
            )
        job: EnqueuedJob = result.data
        response.status_code = 202
        return UserSyncJobAcceptedResponse(
            success=True,
            job_id=job.job_id,
            platform=job.platform,
            user_email=job.user_email,
            dry_run=job.dry_run,
            status="in_progress",
            started_at=job.started_at,
        )

    # Platform sync
    result = enqueue_platform_sync(
        coordinator=coordinator,
        idempotency=idempotency,
        settings=settings,
        platform=request.platform,
        dry_run=request.dry_run,
        request_id=request.request_id or "",
    )
    if not result.is_success or result.data is None:
        raise _http_error_from_enqueue(result.error_code or "", result.message or "")
    job = result.data
    response.status_code = 202
    return PlatformSyncJobAcceptedResponse(
        success=True,
        job_id=job.job_id,
        platform=job.platform,
        dry_run=job.dry_run,
        status="in_progress",
        started_at=job.started_at,
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
