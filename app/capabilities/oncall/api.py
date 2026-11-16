"""Public surface of the on-call capability: the lookup, its domain types and the provider.

Features import this module only (decisions/plugin-architecture.md). ``OnCallLookup`` answers who
is on call for a schedule; the reference's ``system`` selects the source, never a setting. Every
lookup returns an ``OperationResult``: an unknown system is ``PERMANENT_ERROR``
``ADAPTER_NOT_FOUND``, and a source that fails returns its classified status, so the consumer
decides what a missing answer means for it. Unexpected exceptions propagate.
"""

from typing import Protocol

from capabilities.oncall.domain import (
    OPSGENIE,
    ROTATIONS,
    Account,
    OnCallPerson,
    Rotation,
    Schedule,
    ScheduleReference,
    Shift,
)
from contracts.operations.result import OperationResult

__all__ = [
    "OPSGENIE",
    "ROTATIONS",
    "Account",
    "OnCallLookup",
    "OnCallPerson",
    "Rotation",
    "Schedule",
    "ScheduleReference",
    "Shift",
    "configured_rotations",
    "get_oncall_lookup",
]


class OnCallLookup(Protocol):
    """Who is on call, and the schedules, across every schedule source."""

    async def on_call_now(
        self, reference: ScheduleReference, *, rotation: str | None = None
    ) -> OperationResult[tuple[OnCallPerson, ...]]:
        """Return who is on call now for the schedule, optionally for one named rotation.

        An empty tuple means nobody is on call (a coverage gap), not a failure.
        """
        ...

    async def get_schedule(self, reference: ScheduleReference, *, horizon_weeks: int = 12) -> OperationResult[Schedule]:
        """Return the schedule with the active shift and those starting within ``horizon_weeks``."""
        ...

    async def list_schedules(self, system: str) -> OperationResult[tuple[ScheduleReference, ...]]:
        """Return the schedules the system's source itself knows (none for a source keyed by consumer references)."""
        ...


def get_oncall_lookup() -> OnCallLookup:
    """Return the singleton lookup over the self-managed rotations and Opsgenie.

    Opsgenie settings are read at each call, so an unconfigured tenant is a result, not a boot failure.
    """
    from capabilities.oncall.providers import get_oncall_service  # noqa: PLC0415 - providers import the service, which imports this module

    return get_oncall_service()


def configured_rotations() -> tuple[ScheduleReference, ...]:
    """Return the references of the self-managed rotations loaded from the rotation files.

    Synchronous and offline: it reads the loaded files only, so config-time code (job registration)
    can call it inside the running event loop.
    """
    from capabilities.oncall.providers import get_rotation_schedules  # noqa: PLC0415 - providers import the service, which imports this module

    return tuple(schedule.reference for schedule in get_rotation_schedules())
