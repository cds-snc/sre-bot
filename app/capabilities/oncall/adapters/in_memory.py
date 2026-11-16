"""In-memory on-call lookup for tests and local runs, with the real service's observable rules.

One seeded schedule per reference serves both systems: an unknown system is
``ADAPTER_NOT_FOUND``, an unseeded schedule ``NOT_FOUND``, ``get_schedule`` of an Opsgenie
reference ``UNSUPPORTED_OPERATION`` as the Opsgenie source returns it, and ``list_schedules``
answers the seeded self-managed references and none for Opsgenie.
"""

from collections.abc import Mapping

from capabilities.oncall.api import OnCallLookup
from capabilities.oncall.domain import OPSGENIE, ROTATIONS, OnCallPerson, Schedule, ScheduleReference
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus


class InMemoryOnCallLookup(OnCallLookup):
    """``OnCallLookup`` over seeded people (both systems) and seeded schedules (rotations)."""

    def __init__(
        self,
        *,
        people: Mapping[ScheduleReference, tuple[OnCallPerson, ...]] | None = None,
        schedules: Mapping[ScheduleReference, Schedule] | None = None,
    ) -> None:
        self._people = dict(people or {})
        self._schedules = dict(schedules or {})

    async def on_call_now(
        self, reference: ScheduleReference, *, rotation: str | None = None
    ) -> OperationResult[tuple[OnCallPerson, ...]]:
        """Return the seeded people of the schedule (``rotation`` does not narrow them)."""
        if reference.system not in (OPSGENIE, ROTATIONS):
            return _unknown_system(reference.system)
        if reference not in self._people:
            return OperationResult.error(OperationStatus.NOT_FOUND, f"no schedule {reference.id!r}", ErrorCode.NOT_FOUND)
        return OperationResult.success(self._people[reference])

    async def get_schedule(self, reference: ScheduleReference, *, horizon_weeks: int = 12) -> OperationResult[Schedule]:
        """Return the seeded schedule of a rotations reference; Opsgenie schedules are unsupported."""
        if reference.system == OPSGENIE:
            return OperationResult.permanent_error(
                "Opsgenie does not support reading a schedule", ErrorCode.UNSUPPORTED_OPERATION
            )
        if reference.system != ROTATIONS:
            return _unknown_system(reference.system)
        if reference not in self._schedules:
            return OperationResult.error(OperationStatus.NOT_FOUND, f"no rotation {reference.id!r}", ErrorCode.NOT_FOUND)
        return OperationResult.success(self._schedules[reference])

    async def list_schedules(self, system: str) -> OperationResult[tuple[ScheduleReference, ...]]:
        """Return the seeded schedule references of the rotations system and none for Opsgenie."""
        if system == OPSGENIE:
            return OperationResult.success(())
        if system != ROTATIONS:
            return _unknown_system(system)
        return OperationResult.success(tuple(reference for reference in self._schedules if reference.system == ROTATIONS))


def _unknown_system[T](system: str) -> OperationResult[T]:
    return OperationResult.permanent_error(f"no schedule source for system {system!r}", ErrorCode.ADAPTER_NOT_FOUND)
