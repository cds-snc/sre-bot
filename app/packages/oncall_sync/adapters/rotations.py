"""Self-managed rotations read through the on-call capability (decisions/oncall.md).

Implements ``UserRotationsProvider`` over ``capabilities.oncall.api``: the rotations system's
schedules, each one's name and the person on call now. A failed lookup, nobody on call, or a person
without a Slack account leaves that rotation out and logs why, so its usergroup is never written
empty; a failed listing leaves them all out.
"""

import structlog

from capabilities.oncall.api import ROTATIONS, OnCallLookup, ScheduleReference
from contracts.operations.result import OperationResult
from packages.oncall_sync.ports import CurrentUserRotation

logger = structlog.get_logger()

SLACK_PLATFORM = "slack"


class CapabilityUserRotations:
    """``UserRotationsProvider`` over the on-call capability's self-managed rotations."""

    def __init__(self, lookup: OnCallLookup) -> None:
        self._lookup = lookup

    async def get_current_rotations(self) -> list[CurrentUserRotation]:
        """Return each rotation the capability answers for, with its current Slack user."""
        listed = await self._lookup.list_schedules(ROTATIONS)
        if not listed.is_success or listed.data is None:
            _log_lookup_failed(listed, handle=None)
            return []
        current: list[CurrentUserRotation] = []
        for reference in listed.data:
            rotation = await self._current(reference)
            if rotation is not None:
                current.append(rotation)
        return current

    async def _current(self, reference: ScheduleReference) -> CurrentUserRotation | None:
        schedule = await self._lookup.get_schedule(reference, horizon_weeks=0)
        if not schedule.is_success or schedule.data is None:
            _log_lookup_failed(schedule, handle=reference.id)
            return None
        people = await self._lookup.on_call_now(reference)
        if not people.is_success or people.data is None:
            _log_lookup_failed(people, handle=reference.id)
            return None
        slack_ids = [
            person.account.account_id
            for person in people.data
            if person.account is not None and person.account.platform == SLACK_PLATFORM
        ]
        if not slack_ids:
            logger.warning("oncall_sync_user_rotation_skipped", slack_handle=reference.id, reason="no_slack_user_on_call")
            return None
        return CurrentUserRotation(
            slack_usergroup_handle=reference.id,
            slack_usergroup_name=schedule.data.name,
            slack_user_id=slack_ids[0],
        )


def _log_lookup_failed[T](result: OperationResult[T], *, handle: str | None) -> None:
    logger.error(
        "oncall_sync_user_rotation_lookup_failed",
        slack_handle=handle,
        status=result.status.value,
        error=result.message,
        error_code=result.error_code,
    )
