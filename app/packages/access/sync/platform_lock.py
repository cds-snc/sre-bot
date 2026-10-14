"""Sync job concurrency wrappers over the coordination lease facade."""

from typing import Any

from contracts.coordination import LeaseStore
from packages.access.sync.job_status_store import JobStatusStore


def platform_lock_key(platform: str) -> str:
    return f"access_sync:platform_lock:{platform}"


def user_lock_key(platform: str, user_email: str) -> str:
    return f"access_sync:user_lock:{platform}:{user_email.lower()}"


def acquire_lock(
    lock_key: str,
    payload: dict[str, Any],
    lock_store: LeaseStore,
    job_status_store: JobStatusStore,
    ttl_seconds: int,
) -> str | None:
    """Atomically acquire lock and write holder metadata when successful.

    Returns the claim token that release_lock() needs, or None when another job
    holds the lock. The token stays out of the holder record, which pollers read.
    """
    claim_token = lock_store.acquire(lock_key)
    if claim_token is not None:
        job_status_store.put(f"{lock_key}:holder", payload, ttl_seconds=ttl_seconds)
    return claim_token


def current_holder(lock_key: str, job_status_store: JobStatusStore) -> dict[str, Any] | None:
    """Best-effort holder metadata for already-running reporting only."""
    return job_status_store.get(f"{lock_key}:holder")


def release_lock(
    lock_key: str,
    lock_store: LeaseStore,
    claim_token: str,
) -> None:
    """Release the lock claim for future runs, unless another job has taken it over."""
    lock_store.release(lock_key, claim_token)
