from collections.abc import Callable
from typing import Protocol


class BackgroundJobRegistry(Protocol):
    """Scheduler-agnostic registry boundary for feature background jobs.

    This protocol defines the exact contract feature packages must interact with.
    """

    def register(
        self,
        *,
        job_name: str,
        schedule: str,
        job: Callable[[], None],
    ) -> None:
        """Register a recurring background job by name and schedule."""
        ...
