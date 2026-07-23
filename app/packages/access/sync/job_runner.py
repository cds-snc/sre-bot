"""Shared sync job execution for access sync.

Both the HTTP route handler and the Slack command handlers execute the same
underlying job lifecycle through the functions in this module.

Thread lifecycle for user sync:
  1. ``spawn_user_sync_thread`` — acquire lock, write in-progress record, start thread
  2. ``run_user_sync_job`` (background) — execute sync, write final record, release lock

Thread lifecycle for platform sync:
  1. ``spawn_platform_sync_thread`` — acquire lock, write in-progress record, start thread
  2. ``run_platform_sync_job`` (background) — write running sentinel, execute sync,
     write final record, release lock

No transport-specific logic here — HTTP routes and Slack handlers differ only
in how they format the accepted response and status messages.  Both share the
exact same locking, job record shape, and error sanitization semantics.
"""

import threading
from datetime import UTC, datetime

import structlog

from infrastructure.idempotency import IdempotencyService
from packages.access.sync.application import AccessSyncApplicationServicePort
from packages.access.sync.domain import ReconciliationOutcome, SyncOutcome
from packages.access.sync.job_models import (
    CompletedPlatformRecord,
    CompletedUserRecord,
    FailedPlatformRecord,
    FailedUserRecord,
    JobStatus,
    PlatformRunningRecord,
    SyncJobError,
    UserRunningRecord,
)
from packages.access.sync.platform_lock import (
    acquire_lock,
    platform_lock_key,
    release_lock,
    user_lock_key,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Background thread targets
# ---------------------------------------------------------------------------


def run_user_sync_job(
    coordinator: AccessSyncApplicationServicePort,
    idempotency: IdempotencyService,
    job_id: str,
    user_email: str,
    platform: str,
    dry_run: bool,
    request_id: str,
    started_at: str,
    job_ttl_seconds: int,
) -> None:
    """Background thread target: run user sync and persist the outcome.

    Writes a completed or failed record to the idempotency store and releases
    the user lock when done.  All exceptions are caught and sanitized — the
    external error payload always uses ``SyncJobError.SYNC_FAILED`` so
    implementation details do not leak through the job store.
    """
    log = logger.bind(job_id=job_id, user_email=user_email, platform=platform, dry_run=dry_run)
    log.info("user_sync_job_started", correlation_id=request_id)
    record: FailedUserRecord | CompletedUserRecord
    try:
        result = coordinator.sync_user(
            user_email=user_email,
            platform=platform,
            dry_run=dry_run,
            request_id=request_id,
        )
        log.info("user_sync_job_finished", success=result.is_success, error=result.message)
        completed_at = datetime.now(UTC).isoformat()
        if result.is_success and result.data is not None:
            outcome: SyncOutcome = result.data
            record = CompletedUserRecord(
                job_id=job_id,
                user_email=user_email,
                platform=platform,
                dry_run=dry_run,
                started_at=started_at,
                completed_at=completed_at,
                actions_planned=list(outcome.planned_actions),
                actions_applied=list(outcome.applied_actions),
                requires_manual_action=outcome.requires_manual_action,
            )
            log.info(
                "user_sync_job_completed",
                applied=len(outcome.applied_actions),
                dry_run=dry_run,
            )
        else:
            record = FailedUserRecord(
                job_id=job_id,
                user_email=user_email,
                platform=platform,
                dry_run=dry_run,
                started_at=started_at,
                completed_at=completed_at,
                error=result.message or SyncJobError.SYNC_FAILED,
            )
            log.warning(
                "user_sync_job_failed",
                error=result.message,
                error_code=result.error_code,
            )
    except Exception as exc:
        completed_at = datetime.now(UTC).isoformat()
        record = FailedUserRecord(
            job_id=job_id,
            user_email=user_email,
            platform=platform,
            dry_run=dry_run,
            started_at=started_at,
            completed_at=completed_at,
            error=SyncJobError.SYNC_FAILED,
        )
        log.error("user_sync_job_error", error=str(exc), error_type=type(exc).__name__)

    payload = record.to_dict()
    idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)
    release_lock(user_lock_key(platform, user_email), payload, idempotency, job_ttl_seconds)


def run_platform_sync_job(
    coordinator: AccessSyncApplicationServicePort,
    idempotency: IdempotencyService,
    job_id: str,
    platform: str,
    dry_run: bool,
    request_id: str,
    started_at: str,
    job_ttl_seconds: int,
) -> None:
    """Background thread target: run platform sync and persist the outcome.

    Writes an in-progress sentinel immediately so status polling returns a
    meaningful state before the full reconciliation completes.
    """
    log = logger.bind(job_id=job_id, platform=platform, dry_run=dry_run)
    log.info(
        "platform_sync_job_started",
        correlation_id=request_id,
        poll_path=f"/api/v1/access/sync-runs/{job_id}",
    )
    idempotency.set(
        job_id,
        PlatformRunningRecord(
            job_id=job_id,
            platform=platform,
            dry_run=dry_run,
            started_at=started_at,
            status=JobStatus.IN_PROGRESS,
        ).to_dict(),
        ttl_seconds=job_ttl_seconds,
    )
    record: FailedPlatformRecord | CompletedPlatformRecord
    try:
        result = coordinator.sync_platform(
            platform=platform,
            dry_run=dry_run,
            request_id=request_id,
        )
        completed_at = datetime.now(UTC).isoformat()
        if result.is_success and result.data is not None:
            recon: ReconciliationOutcome = result.data
            record = CompletedPlatformRecord(
                job_id=job_id,
                platform=platform,
                dry_run=dry_run,
                started_at=started_at,
                completed_at=completed_at,
                users_synced=recon.users_synced,
                users_converged=recon.users_converged,
                orphans_found=recon.orphans_found,
                requires_manual_action_count=recon.requires_manual_action_count,
                changed_user_count=recon.changed_user_count,
                unchanged_user_count=recon.unchanged_user_count,
                action_counts=dict(recon.action_counts),
                lifecycle_actions={action: list(users) for action, users in recon.lifecycle_actions.items()},
                entitlements_by_action={
                    action: {slug: list(users) for slug, users in by_slug.items()}
                    for action, by_slug in recon.entitlements_by_action.items()
                },
            )
            log.info(
                "platform_sync_job_completed",
                users_synced=recon.users_synced,
                users_converged=recon.users_converged,
                orphans_found=recon.orphans_found,
                requires_manual_action_count=recon.requires_manual_action_count,
                dry_run=dry_run,
            )
        else:
            record = FailedPlatformRecord(
                job_id=job_id,
                platform=platform,
                dry_run=dry_run,
                started_at=started_at,
                completed_at=completed_at,
                error=result.message or SyncJobError.SYNC_FAILED,
            )
            log.warning(
                "platform_sync_job_failed",
                error=result.message,
                error_code=result.error_code,
            )
    except Exception as exc:
        completed_at = datetime.now(UTC).isoformat()
        record = FailedPlatformRecord(
            job_id=job_id,
            platform=platform,
            dry_run=dry_run,
            started_at=started_at,
            completed_at=completed_at,
            error=SyncJobError.SYNC_FAILED,
        )
        log.error(
            "platform_sync_job_error",
            error=str(exc),
            error_type=type(exc).__name__,
        )

    payload = record.to_dict()
    idempotency.set(job_id, payload, ttl_seconds=job_ttl_seconds)
    release_lock(platform_lock_key(platform), payload, idempotency, job_ttl_seconds)


# ---------------------------------------------------------------------------
# Thread spawn helpers (acquire lock + start thread)
# ---------------------------------------------------------------------------


def spawn_user_sync_thread(
    coordinator: AccessSyncApplicationServicePort,
    idempotency: IdempotencyService,
    job_id: str,
    user_email: str,
    platform: str,
    dry_run: bool,
    request_id: str,
    started_at: str,
    job_ttl_seconds: int,
) -> None:
    """Acquire user sync lock, write initial record, and start background thread.

    After this returns the caller can immediately return an accepted response;
    the background thread will update the idempotency record when done.
    """
    lock_record = UserRunningRecord(
        job_id=job_id,
        user_email=user_email,
        platform=platform,
        dry_run=dry_run,
        started_at=started_at,
    )
    acquire_lock(
        user_lock_key(platform, user_email),
        lock_record.to_dict(),
        idempotency,
        job_ttl_seconds,
    )
    job_record = {**lock_record.to_dict(), "status": JobStatus.IN_PROGRESS}
    idempotency.set(job_id, job_record, ttl_seconds=job_ttl_seconds)
    thread = threading.Thread(
        target=run_user_sync_job,
        kwargs={
            "coordinator": coordinator,
            "idempotency": idempotency,
            "job_id": job_id,
            "user_email": user_email,
            "platform": platform,
            "dry_run": dry_run,
            "request_id": request_id,
            "started_at": started_at,
            "job_ttl_seconds": job_ttl_seconds,
        },
        daemon=True,
        name=f"user-sync-{job_id[:8]}",
    )
    thread.start()


def spawn_platform_sync_thread(
    coordinator: AccessSyncApplicationServicePort,
    idempotency: IdempotencyService,
    job_id: str,
    platform: str,
    dry_run: bool,
    request_id: str,
    started_at: str,
    job_ttl_seconds: int,
) -> None:
    """Acquire platform sync lock, write initial record, and start background thread."""
    lock_record = PlatformRunningRecord(
        job_id=job_id,
        platform=platform,
        dry_run=dry_run,
        started_at=started_at,
    )
    acquire_lock(
        platform_lock_key(platform),
        lock_record.to_dict(),
        idempotency,
        job_ttl_seconds,
    )
    job_record = {**lock_record.to_dict(), "status": JobStatus.IN_PROGRESS}
    idempotency.set(job_id, job_record, ttl_seconds=job_ttl_seconds)
    thread = threading.Thread(
        target=run_platform_sync_job,
        kwargs={
            "coordinator": coordinator,
            "idempotency": idempotency,
            "job_id": job_id,
            "platform": platform,
            "dry_run": dry_run,
            "request_id": request_id,
            "started_at": started_at,
            "job_ttl_seconds": job_ttl_seconds,
        },
        daemon=True,
        name=f"platform-sync-{job_id[:8]}",
    )
    thread.start()
