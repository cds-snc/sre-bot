"""The Protocol capabilities.oncall's service depends on, implemented in adapters/."""

from typing import Protocol

from capabilities.oncall.domain import OnCallPerson, Schedule, ScheduleReference
from contracts.operations.result import OperationResult


class ScheduleSource(Protocol):
    """One schedule source system; the service routes a reference to it by ``ScheduleReference.system``."""

    async def on_call_now(
        self, reference: ScheduleReference, *, rotation: str | None = None
    ) -> OperationResult[tuple[OnCallPerson, ...]]:
        """Return who is on call now for the schedule, optionally for one named rotation."""
        ...

    async def get_schedule(self, reference: ScheduleReference, *, horizon_weeks: int = 12) -> OperationResult[Schedule]:
        """Return the schedule with its shifts through the horizon."""
        ...

    async def list_schedules(self) -> OperationResult[tuple[ScheduleReference, ...]]:
        """Return the schedules the source itself knows."""
        ...
