"""Scheduler-agnostic registry Protocol every recurring job registers through."""

from collections.abc import Callable
from datetime import timedelta
from typing import Protocol

from contracts.services import ServiceScopeOpener


class BackgroundJobRegistry(Protocol):
    """Scheduler-agnostic registry boundary for recurring jobs.

    Feature plugins register through it, and so do the host's own jobs and the
    legacy jobs the scheduler still hand-imports: the host applies the error
    boundary and, for a Tier-2 job, the lease, so a registration declares its
    schedule and tier only (decisions/reliability.md).
    """

    @property
    def service_scopes(self) -> ServiceScopeOpener:
        """Opens a per-invocation service scope for a job to resolve contracts in."""
        ...

    def register_daily(
        self,
        *,
        job_name: str,
        schedule: str,
        job: Callable[[], None],
        lease_ttl: timedelta | None = None,
    ) -> None:
        """Register a job that runs once per day at ``schedule`` (``"HH:MM"``, UTC).

        The first run is at the next ``HH:MM`` after registration. ``lease_ttl`` as
        for ``register_interval``.
        """
        ...

    def register_interval(
        self,
        *,
        job_name: str,
        every: timedelta,
        job: Callable[[], None],
        lease_ttl: timedelta | None = None,
    ) -> None:
        """Register a job that runs repeatedly at the given interval.

        The first run is one interval after registration, so every deploy restarts
        the count; the next run is counted from the end of the previous one.
        ``lease_ttl`` None (the default) is Tier-1: the job runs on every replica. A
        value is Tier-2: each run first takes a lease of that length, so at most one
        replica runs it at a time. The lease only avoids duplicate runs; the job body
        must stay idempotent. The TTL comes from the job's own settings and is sized
        to its longest run (decisions/reliability.md); one under a second is rejected.
        """
        ...
