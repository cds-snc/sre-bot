"""Host lease enforcement: run a job only while holding its lease."""

from collections.abc import Callable

from contracts.coordination import LeaseStore


def run_if_leased(lease_store: LeaseStore, name: str, job: Callable[[], None]) -> None:
    """Acquire a lease, run the job, and always release on completion."""
    claim_token = lease_store.acquire(name)
    if claim_token is None:
        return

    try:
        job()
    finally:
        lease_store.release(name, claim_token)
