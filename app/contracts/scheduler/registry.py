"""Scheduler-agnostic registry Protocol feature packages register background jobs through."""

from collections.abc import Callable
from datetime import timedelta
from typing import Protocol


class BackgroundJobRegistry(Protocol):
    """Scheduler-agnostic registry boundary for feature background jobs.

    This protocol defines the exact contract feature packages must interact with.
    """

    def register_daily(
        self,
        *,
        job_name: str,
        schedule: str,
        job: Callable[[], None],
    ) -> None:
        """Register a job that runs once per day at ``schedule`` (``"HH:MM"``, UTC)."""
        ...

    def register_interval(
        self,
        *,
        job_name: str,
        every: timedelta,
        job: Callable[[], None],
    ) -> None:
        """Register a job that runs repeatedly at the given interval."""
        ...
