"""Host lease enforcement: run a job only while holding its lease."""

import time
from collections.abc import Callable
from datetime import timedelta

from contracts.coordination import LeaseStore


def run_if_leased(
    lease_store: LeaseStore,
    name: str,
    job: Callable[[], None],
    *,
    min_hold: timedelta | None = None,
) -> None:
    """Acquire a lease, run the job, and always release or hold it on completion.

    Without `min_hold` the lease is released when the job ends. With it, a run
    that ends before start plus `min_hold`, failed runs included, keeps the lease
    until then, so another replica whose tick comes a moment later does not run
    the same tick again; a run that ends past it releases at once (ShedLock's
    lockAtLeastFor). The lease TTL stays the maximum hold: callers keep `min_hold`
    within it.
    """
    start = time.time()
    claim_token = lease_store.acquire(name)
    if claim_token is None:
        return

    try:
        job()
    finally:
        not_before = None if min_hold is None else start + min_hold.total_seconds()
        lease_store.release(name, claim_token, not_before=not_before)
