"""Shared lease helpers over the idempotency claim/release primitive.

These helpers provide reusable singleton-execution semantics for callers that
need mutual exclusion but do not need deduplication outcomes.
"""

from collections.abc import Callable
from functools import cache

from infrastructure.idempotency.factory import build_idempotency_store
from infrastructure.idempotency.protocol import IdempotencyStore


def acquire_lease(lock_store: IdempotencyStore, name: str) -> str | None:
    """Attempt to acquire a named lease.

    Returns the claim token when this caller won the claim and should proceed,
    None otherwise. The token is what release_lease() needs to free the lease.
    """
    return lock_store.claim(name).claim_token


def release_lease(lock_store: IdempotencyStore, name: str, claim_token: str) -> bool:
    """Release a lease this caller holds.

    Returns False, changing nothing, when the lease expired and another caller
    took it over: a stale holder never frees a live holder's lease.
    """
    return lock_store.release(name, claim_token)


@cache
def get_lease_store(ttl_seconds: int) -> IdempotencyStore:
    """Return a lease store singleton for the provided in-progress TTL."""
    return build_idempotency_store(in_progress_ttl_seconds=ttl_seconds)


def run_if_leased(lock_store: IdempotencyStore, name: str, job: Callable[[], None]) -> None:
    """Acquire a lease, run the job, and always release on completion."""
    claim_token = acquire_lease(lock_store, name)
    if claim_token is None:
        return

    try:
        job()
    finally:
        release_lease(lock_store, name, claim_token)
