"""Shared admission logic for all Access Sync transports.

Both the HTTP route handler and the Slack command handlers admit sync requests
through these shared functions so that the enabled-check, lock-check, and job
spawn behaviour is identical regardless of the calling transport.

Transports are responsible only for request parsing and response formatting.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

import structlog

from infrastructure.idempotency import IdempotencyService
from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.application import AccessSyncApplicationServicePort
from packages.access.sync.job_runner import (
    spawn_platform_sync_thread,
    spawn_user_sync_thread,
)
from packages.access.sync.platform_lock import (
    check_lock,
    platform_lock_key,
    user_lock_key,
)

logger = structlog.get_logger()


class _IngressSettings(Protocol):
    """Structural contract for the settings object consumed by ingress functions."""

    enabled: bool
    job_ttl_seconds: int
    lock_stale_seconds: int


@dataclass(frozen=True)
class EnqueuedJob:
    """Neutral job receipt returned by the ingress layer to all transports."""

    job_id: str
    platform: str
    user_email: str
    dry_run: bool
    started_at: str
    already_running: bool


def enqueue_user_sync(
    coordinator: AccessSyncApplicationServicePort,
    idempotency: IdempotencyService,
    settings: _IngressSettings,
    user_email: str,
    platform: str,
    dry_run: bool = False,
    request_id: str = "",
) -> OperationResult:
    """Admit a user sync request through the shared ingress path.

    Checks the feature flag, detects duplicate runs, and spawns the background
    job.  Returns ``OperationResult[EnqueuedJob]``.

    Error codes:
        FEATURE_DISABLED — feature flag is off.
    """
    if not settings.enabled:
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Access Sync is not enabled",
            error_code="FEATURE_DISABLED",
        )

    lock_key = user_lock_key(platform, user_email)
    running = check_lock(lock_key, idempotency, settings.lock_stale_seconds)
    if running is not None:
        existing_job_id = running.get("job_id", "")
        logger.bind(platform=platform, user_email=user_email).info("user_sync_already_running", existing_job_id=existing_job_id)
        return OperationResult.success(
            data=EnqueuedJob(
                job_id=existing_job_id,
                platform=platform,
                user_email=user_email,
                dry_run=running.get("dry_run", dry_run),
                started_at=running.get("started_at", ""),
                already_running=True,
            )
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now(UTC).isoformat()
    spawn_user_sync_thread(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id=job_id,
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
        request_id=request_id or job_id,
        started_at=started_at,
        job_ttl_seconds=settings.job_ttl_seconds,
    )
    return OperationResult.success(
        data=EnqueuedJob(
            job_id=job_id,
            platform=platform,
            user_email=user_email,
            dry_run=dry_run,
            started_at=started_at,
            already_running=False,
        )
    )


def enqueue_platform_sync(
    coordinator: AccessSyncApplicationServicePort,
    idempotency: IdempotencyService,
    settings: _IngressSettings,
    platform: str,
    dry_run: bool = False,
    request_id: str = "",
) -> OperationResult:
    """Admit a platform sync request through the shared ingress path.

    Checks the feature flag, detects duplicate runs, and spawns the background
    job.  Returns ``OperationResult[EnqueuedJob]``.

    Error codes:
        FEATURE_DISABLED — feature flag is off.
    """
    if not settings.enabled:
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message="Access Sync is not enabled",
            error_code="FEATURE_DISABLED",
        )

    lock_key = platform_lock_key(platform)
    running = check_lock(lock_key, idempotency, settings.lock_stale_seconds)
    if running is not None:
        existing_job_id = running.get("job_id", "")
        logger.bind(platform=platform).info("platform_sync_already_running", existing_job_id=existing_job_id)
        return OperationResult.success(
            data=EnqueuedJob(
                job_id=existing_job_id,
                platform=platform,
                user_email="",
                dry_run=running.get("dry_run", dry_run),
                started_at=running.get("started_at", ""),
                already_running=True,
            )
        )

    job_id = str(uuid.uuid4())
    started_at = datetime.now(UTC).isoformat()
    spawn_platform_sync_thread(
        coordinator=coordinator,
        idempotency=idempotency,
        job_id=job_id,
        platform=platform,
        dry_run=dry_run,
        request_id=request_id or job_id,
        started_at=started_at,
        job_ttl_seconds=settings.job_ttl_seconds,
    )
    return OperationResult.success(
        data=EnqueuedJob(
            job_id=job_id,
            platform=platform,
            user_email="",
            dry_run=dry_run,
            started_at=started_at,
            already_running=False,
        )
    )
