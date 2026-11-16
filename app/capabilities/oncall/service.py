"""On-call service: routes each lookup to the schedule source named by the reference's system."""

from collections.abc import Mapping

import structlog

from capabilities.oncall.api import OnCallLookup
from capabilities.oncall.domain import OnCallPerson, Schedule, ScheduleReference
from capabilities.oncall.interfaces import ScheduleSource
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult

logger = structlog.get_logger()


class OnCallService(OnCallLookup):
    """``OnCallLookup`` over the sources it holds, keyed by system; source results pass through unchanged."""

    def __init__(self, sources: Mapping[str, ScheduleSource]) -> None:
        self._sources = dict(sources)

    async def on_call_now(
        self, reference: ScheduleReference, *, rotation: str | None = None
    ) -> OperationResult[tuple[OnCallPerson, ...]]:
        """Return who is on call now for the schedule, or the source's error result."""
        source = self._source(reference.system)
        if source is None:
            return _unknown_system(reference.system)
        return await source.on_call_now(reference, rotation=rotation)

    async def get_schedule(self, reference: ScheduleReference, *, horizon_weeks: int = 12) -> OperationResult[Schedule]:
        """Return the schedule through the horizon, or the source's error result."""
        source = self._source(reference.system)
        if source is None:
            return _unknown_system(reference.system)
        return await source.get_schedule(reference, horizon_weeks=horizon_weeks)

    async def list_schedules(self, system: str) -> OperationResult[tuple[ScheduleReference, ...]]:
        """Return the schedules the system's source knows, or the source's error result."""
        source = self._source(system)
        if source is None:
            return _unknown_system(system)
        return await source.list_schedules()

    def _source(self, system: str) -> ScheduleSource | None:
        return self._sources.get(system)


def _unknown_system[T](system: str) -> OperationResult[T]:
    logger.warning("oncall_unknown_system", system=system)
    return OperationResult.permanent_error(f"no schedule source for system {system!r}", ErrorCode.ADAPTER_NOT_FOUND)
