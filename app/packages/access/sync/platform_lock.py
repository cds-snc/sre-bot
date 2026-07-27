"""Sync job concurrency wrappers over the shared infrastructure lease primitive."""

from typing import Any

from infrastructure.idempotency import IdempotencyService, IdempotencyStore, acquire_lease, release_lease


def platform_lock_key(platform: str) -> str:
    return f"access_sync:platform_lock:{platform}"


def user_lock_key(platform: str, user_email: str) -> str:
    return f"access_sync:user_lock:{platform}:{user_email.lower()}"


def acquire_lock(
    lock_key: str,
    payload: dict[str, Any],
    lock_store: IdempotencyStore,
    idempotency: IdempotencyService,
    ttl_seconds: int,
) -> bool:
    """Atomically acquire lock and write holder metadata when successful."""
    acquired = acquire_lease(lock_store, lock_key)
    if acquired:
        idempotency.set(f"{lock_key}:holder", payload, ttl_seconds=ttl_seconds)
    return acquired


def current_holder(lock_key: str, idempotency: IdempotencyService) -> dict[str, Any] | None:
    """Best-effort holder metadata for already-running reporting only."""
    return idempotency.get(f"{lock_key}:holder")


def release_lock(
    lock_key: str,
    lock_store: IdempotencyStore,
) -> None:
    """Release lock claim for future runs."""
    release_lease(lock_store, lock_key)
