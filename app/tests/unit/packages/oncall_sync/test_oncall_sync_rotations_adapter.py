"""Unit tests for oncall_sync's self-managed rotations adapter over the on-call capability.

The adapter runs over ``InMemoryOnCallLookup`` (the capability's fake at the ``OnCallLookup``
seam), or a stub lookup whose calls fail, and is awaited directly. Assertions are on the current
rotations it returns: a rotation the capability cannot answer for, or answers with nobody or a
person without a Slack account, is left out, so the job never writes that usergroup empty.
"""

from datetime import UTC, datetime

import pytest

from capabilities.oncall.adapters.in_memory import InMemoryOnCallLookup
from capabilities.oncall.api import (
    ROTATIONS,
    Account,
    OnCallPerson,
    Rotation,
    Schedule,
    ScheduleReference,
)
from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from packages.oncall_sync.adapters.rotations import CapabilityUserRotations
from packages.oncall_sync.ports import CurrentUserRotation

pytestmark = pytest.mark.unit

START = datetime(2026, 1, 5, 9, tzinfo=UTC)


def _slack(member_id: str) -> OnCallPerson:
    return OnCallPerson(email=None, account=Account("slack", None, member_id))


def _schedule(handle: str, name: str, *members: OnCallPerson) -> Schedule:
    reference = ScheduleReference(ROTATIONS, handle)
    return Schedule(reference, name, (Rotation(name, members, 1, START),), ())


def _lookup(people: dict[str, tuple[OnCallPerson, ...]], *schedules: Schedule) -> InMemoryOnCallLookup:
    return InMemoryOnCallLookup(
        people={ScheduleReference(ROTATIONS, handle): who for handle, who in people.items()},
        schedules={schedule.reference: schedule for schedule in schedules},
    )


async def test_each_rotation_maps_to_its_usergroup_and_current_slack_user() -> None:
    lookup = _lookup(
        {"triage": (_slack("U0TRIAGE"),), "review": (_slack("U0REVIEW"),)},
        _schedule("triage", "Triage", _slack("U0TRIAGE")),
        _schedule("review", "Review", _slack("U0REVIEW")),
    )

    current = await CapabilityUserRotations(lookup).get_current_rotations()

    assert current == [
        CurrentUserRotation(slack_usergroup_handle="triage", slack_usergroup_name="Triage", slack_user_id="U0TRIAGE"),
        CurrentUserRotation(slack_usergroup_handle="review", slack_usergroup_name="Review", slack_user_id="U0REVIEW"),
    ]


async def test_a_rotation_whose_lookup_fails_is_skipped_and_the_next_still_answers() -> None:
    lookup = _lookup(
        {"review": (_slack("U0REVIEW"),)},
        _schedule("triage", "Triage", _slack("U0TRIAGE")),
        _schedule("review", "Review", _slack("U0REVIEW")),
    )

    current = await CapabilityUserRotations(lookup).get_current_rotations()

    assert [rotation.slack_usergroup_handle for rotation in current] == ["review"]


async def test_a_rotation_with_nobody_on_call_is_skipped_never_emptied() -> None:
    lookup = _lookup({"triage": ()}, _schedule("triage", "Triage", _slack("U0TRIAGE")))

    assert await CapabilityUserRotations(lookup).get_current_rotations() == []


async def test_a_person_without_a_slack_account_is_skipped() -> None:
    by_email = OnCallPerson(email="ann@example.org", account=None)
    lookup = _lookup({"triage": (by_email,)}, _schedule("triage", "Triage", by_email))

    assert await CapabilityUserRotations(lookup).get_current_rotations() == []


class _FailingListLookup(InMemoryOnCallLookup):
    async def list_schedules(self, system: str) -> OperationResult[tuple[ScheduleReference, ...]]:
        return OperationResult.transient_error("source unavailable", ErrorCode.TIMEOUT)


async def test_a_failed_rotation_listing_returns_no_rotations() -> None:
    lookup = _FailingListLookup(schedules={ScheduleReference(ROTATIONS, "triage"): _schedule("triage", "Triage", _slack("U1"))})

    assert await CapabilityUserRotations(lookup).get_current_rotations() == []
