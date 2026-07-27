"""Shared lease helpers over the idempotency claim/release primitive.

These helpers provide reusable singleton-execution semantics for callers that
need mutual exclusion but do not need deduplication outcomes.
"""

from infrastructure.idempotency.protocol import ClaimResult, IdempotencyStore


def acquire_lease(lock_store: IdempotencyStore, name: str) -> bool:
    """Attempt to acquire a named lease.

    Returns True only when this caller won the claim and should proceed.
    """
    return lock_store.claim(name).result is ClaimResult.NEW


def release_lease(lock_store: IdempotencyStore, name: str) -> None:
    """Release a previously-acquired lease."""
    lock_store.release(name)
