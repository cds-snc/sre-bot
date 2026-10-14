"""Shared lease helpers over the conditional-write claim/release primitive.

These helpers provide reusable singleton-execution semantics for callers that
need mutual exclusion but do not need deduplication outcomes.
"""

from collections.abc import Callable
from functools import cache

from contracts.coordination import ConditionalWriteStore
from infrastructure.coordination.factory import build_conditional_write_store


def acquire_lease(lock_store: ConditionalWriteStore, name: str) -> str | None:
    """Attempt to acquire a named lease.

    Returns the claim token when this caller won the claim and should proceed,
    None otherwise. The token is what release_lease() needs to free the lease.
    """
    return lock_store.claim(name).claim_token


def release_lease(lock_store: ConditionalWriteStore, name: str, claim_token: str) -> bool:
    """Release a lease this caller holds.

    Returns False, changing nothing, when the lease expired and another caller
    took it over: a stale holder never frees a live holder's lease.
    """
    return lock_store.release(name, claim_token)


@cache
def get_lease_store(ttl_seconds: int) -> ConditionalWriteStore:
    """Return a lease store singleton for the provided in-progress TTL."""
    return build_conditional_write_store(in_progress_ttl_seconds=ttl_seconds)


def run_if_leased(lock_store: ConditionalWriteStore, name: str, job: Callable[[], None]) -> None:
    """Acquire a lease, run the job, and always release on completion."""
    claim_token = acquire_lease(lock_store, name)
    if claim_token is None:
        return

    try:
        job()
    finally:
        release_lease(lock_store, name, claim_token)
