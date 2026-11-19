"""Lease facade over the conditional-write primitive."""

import time
from typing import final

from contracts.coordination.policy import ReadFailurePolicy, resolve_indeterminate
from contracts.coordination.store import ConditionalWriteStore


@final
class LeaseStore:
    """Named mutual-exclusion leases: acquire returns a token, release gives it back.

    The lease's TTL is the store's in-progress TTL. An expired lease can be taken
    over by another caller; the stale holder's release then returns False and
    frees nothing. A release with a future `not_before` holds the lease until that
    instant instead of freeing it (ShedLock's lockAtLeastFor); the TTL stays the
    maximum hold.
    """

    def __init__(self, store: ConditionalWriteStore, *, read_failure_policy: ReadFailurePolicy) -> None:
        self._store = store
        self._read_failure_policy = read_failure_policy

    def acquire(self, name: str) -> str | None:
        """Return the claim token when this caller holds the lease, None otherwise."""
        return resolve_indeterminate(self._store.claim(name), self._read_failure_policy).claim_token

    def release(self, name: str, claim_token: str, *, not_before: float | None = None) -> bool:
        """Release a lease this caller holds, or hold it until `not_before` (epoch seconds).

        None or a past instant frees the lease now. A future instant keeps it held
        through that instant and frees it after, through the primitive's expire_at,
        never a delete. The instant is floored to the store's whole second: the
        store holds through its expiry second inclusive, so the hold still covers
        `not_before`, and it never passes the expiry the acquire set.

        Returns False, changing nothing, when the lease expired and another caller
        took it over: a stale holder never frees or holds a live holder's lease.
        """
        if not_before is None or not_before <= time.time():
            return self._store.release(name, claim_token)
        return self._store.expire_at(name, claim_token, int(not_before))
