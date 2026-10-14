"""Lease facade over the conditional-write primitive."""

from typing import final

from contracts.coordination.policy import ReadFailurePolicy, resolve_indeterminate
from contracts.coordination.store import ConditionalWriteStore


@final
class LeaseStore:
    """Named mutual-exclusion leases: acquire returns a token, release gives it back.

    The lease's TTL is the store's in-progress TTL. An expired lease can be taken
    over by another caller; the stale holder's release then returns False and
    frees nothing.
    """

    def __init__(self, store: ConditionalWriteStore, *, read_failure_policy: ReadFailurePolicy) -> None:
        self._store = store
        self._read_failure_policy = read_failure_policy

    def acquire(self, name: str) -> str | None:
        """Return the claim token when this caller holds the lease, None otherwise."""
        return resolve_indeterminate(self._store.claim(name), self._read_failure_policy).claim_token

    def release(self, name: str, claim_token: str) -> bool:
        """Release a lease this caller holds.

        Returns False, changing nothing, when the lease expired and another caller
        took it over: a stale holder never frees a live holder's lease.
        """
        return self._store.release(name, claim_token)
