"""Sync job concurrency wrappers over the shared infrastructure lease primitive."""

from typing import Any

from infrastructure.idempotency import IdempotencyStore, acquire_lease, release_lease
from packages.access.sync.job_status_store import JobStatusStore


def platform_lock_key(platform: str) -> str:
    return f"access_sync:platform_lock:{platform}"


def user_lock_key(platform: str, user_email: str) -> str:
    return f"access_sync:user_lock:{platform}:{user_email.lower()}"


def acquire_lock(
    lock_key: str,
    payload: dict[str, Any],
    lock_store: IdempotencyStore,
    job_status_store: JobStatusStore,
    ttl_seconds: int,
) -> bool:
    """Atomically acquire lock and write holder metadata when successful."""
    acquired = acquire_lease(lock_store, lock_key)
    if acquired:
        job_status_store.put(f"{lock_key}:holder", payload, ttl_seconds=ttl_seconds)
    return acquired


def current_holder(lock_key: str, job_status_store: JobStatusStore) -> dict[str, Any] | None:
    """Best-effort holder metadata for already-running reporting only."""
    return job_status_store.get(f"{lock_key}:holder")


def release_lock(
    lock_key: str,
    lock_store: IdempotencyStore,
) -> None:
    """Release lock claim for future runs."""
    release_lease(lock_store, lock_key)
