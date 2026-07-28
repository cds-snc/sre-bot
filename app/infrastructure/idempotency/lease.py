"""Shared lease helpers over the idempotency claim/release primitive.

These helpers provide reusable singleton-execution semantics for callers that
need mutual exclusion but do not need deduplication outcomes.
"""

from collections.abc import Callable
from functools import cache

from infrastructure.idempotency.factory import build_idempotency_store
from infrastructure.idempotency.protocol import ClaimResult, IdempotencyStore


def acquire_lease(lock_store: IdempotencyStore, name: str) -> bool:
    """Attempt to acquire a named lease.

    Returns True only when this caller won the claim and should proceed.
    """
    return lock_store.claim(name).result is ClaimResult.NEW


def release_lease(lock_store: IdempotencyStore, name: str) -> None:
    """Release a previously-acquired lease."""
    lock_store.release(name)


@cache
def get_lease_store(ttl_seconds: int) -> IdempotencyStore:
    """Return a lease store singleton for the provided in-progress TTL."""
    return build_idempotency_store(in_progress_ttl_seconds=ttl_seconds)


def run_if_leased(lock_store: IdempotencyStore, name: str, job: Callable[[], None]) -> None:
    """Acquire a lease, run the job, and always release on completion."""
    if not acquire_lease(lock_store, name):
        return

    try:
        job()
    finally:
        release_lease(lock_store, name)
