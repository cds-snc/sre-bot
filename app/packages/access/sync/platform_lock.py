"""Sync job concurrency guard.

Prevents duplicate concurrent sync jobs for the same target.  Lock records
are stored in ``IdempotencyService`` under a stable key separate from the
per-job UUID so the check is O(1) and visible across HTTP and other transports.

A running lock older than ``lock_stale_after_seconds`` (passed by the caller
from ``AccessSyncSettings``) is treated as stale so a crashed background
thread cannot block future syncs indefinitely.
"""

from datetime import UTC, datetime
from typing import Any

from infrastructure.idempotency import IdempotencyService


def platform_lock_key(platform: str) -> str:
    return f"access_sync:platform_lock:{platform}"


def user_lock_key(platform: str, user_email: str) -> str:
    return f"access_sync:user_lock:{platform}:{user_email.lower()}"


def check_lock(
    key: str,
    idempotency: IdempotencyService,
    lock_stale_after_seconds: int,
) -> dict[str, Any] | None:
    """Return the running job record if an active lock exists, else None.

    Returns None when no record exists, status is not "running", or the lock
    is older than lock_stale_after_seconds.
    """
    record = idempotency.get(key)
    if record is None or record.get("status") != "running":
        return None
    started_at_raw: str = record.get("started_at", "")
    if started_at_raw:
        try:
            elapsed = (datetime.now(UTC) - datetime.fromisoformat(started_at_raw)).total_seconds()
            if elapsed > lock_stale_after_seconds:
                return None
        except ValueError:
            pass
    return record


def acquire_lock(
    key: str,
    payload: dict[str, Any],
    idempotency: IdempotencyService,
    ttl_seconds: int,
) -> None:
    """Write a lock record. Call before spawning the background thread."""
    idempotency.set(key, payload, ttl_seconds=ttl_seconds)


def release_lock(
    key: str,
    final_payload: dict[str, Any],
    idempotency: IdempotencyService,
    ttl_seconds: int,
) -> None:
    """Overwrite the lock with the final completed/failed payload."""
    idempotency.set(key, final_payload, ttl_seconds=ttl_seconds)
