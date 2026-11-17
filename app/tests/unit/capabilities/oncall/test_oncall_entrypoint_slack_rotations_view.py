"""Unit tests for the on-call capability's ``/sre rotations`` Slack entry point.

The handlers run over ``InMemoryOnCallLookup`` (the capability's own fake at the ``OnCallLookup``
seam) seeded with rotation schedules, and a ``FakeSlackReply`` recording the modal it opens.
Assertions are on the registered commands, the ephemeral responses and the modal text Slack
would render, which are the same as before the commands moved into the capability.
"""

from datetime import UTC, datetime

import pytest

from capabilities.oncall.adapters.in_memory import InMemoryOnCallLookup
from capabilities.oncall.api import ROTATIONS, Account, OnCallPerson, Rotation, Schedule, ScheduleReference, Shift
from capabilities.oncall.entrypoints.slack import handle_rotations_help, handle_view_command, register_commands
from contracts.operations import OperationResult, OperationStatus
from contracts.slack.models import CommandPayload
from tests.factories.slack import FakeSlackRegistrar, FakeSlackReply

pytestmark = pytest.mark.unit

HANDLE = "fielding-questions"


def _person(member_id: str) -> OnCallPerson:
    return OnCallPerson(email=None, account=Account("slack", None, member_id))


def _lookup(*shifts: Shift) -> InMemoryOnCallLookup:
    reference = ScheduleReference(ROTATIONS, HANDLE)
    rotation = Rotation("Fielding questions", tuple(shift.person for shift in shifts), 1, shifts[0].start)
    return InMemoryOnCallLookup(schedules={reference: Schedule(reference, "Fielding questions", (rotation,), shifts)})


def _two_shifts() -> tuple[Shift, Shift]:
    return (
        Shift(_person("U1"), datetime(2026, 9, 14, 9, tzinfo=UTC), datetime(2026, 9, 21, 9, tzinfo=UTC)),
        Shift(_person("U2"), datetime(2026, 9, 21, 9, tzinfo=UTC), datetime(2026, 9, 28, 9, tzinfo=UTC)),
    )


def test_register_commands_adds_rotations_help_and_view_under_sre() -> None:
    registrar = FakeSlackRegistrar()

    register_commands(registrar)

    assert [(entry["command"], entry["parent"]) for entry in registrar.commands] == [
        ("rotations", "sre"),
        ("view", "sre.rotations"),
    ]
    parent, view = registrar.commands
    assert parent["handler"] is handle_rotations_help
    assert view["usage_hint"] == "<usergroup-handle>"


def test_rotations_help_lists_the_view_command_and_the_capability_readme() -> None:
    response = handle_rotations_help(CommandPayload(text="", user_id="U1"))

    assert response.ephemeral is True
    assert "Manage user rotations" in response.message
    assert "app/capabilities/oncall/README.md" in response.message


def test_view_command_opens_modal_with_one_line_per_shift() -> None:
    reply = FakeSlackReply()
    payload = CommandPayload(text="", user_id="U1", platform_metadata={"trigger_id": "trigger"})

    response = handle_view_command(payload, {"usergroup_handle": HANDLE}, reply, _lookup(*_two_shifts()))

    assert response.message == ""
    assert response.ephemeral is True
    (kwargs,) = reply.calls_to("open_view")
    assert kwargs["trigger_id"] == "trigger"
    text = kwargs["view"]["blocks"][0]["text"]["text"]
    assert text.splitlines() == [
        "<@U1> | <!date^1789376400^{date_short} {time}|2026-09-14 09:00 UTC> - <!date^1789981200^{date_short} {time}|2026-09-21 09:00 UTC>",
        "<@U2> | <!date^1789981200^{date_short} {time}|2026-09-21 09:00 UTC> - <!date^1790586000^{date_short} {time}|2026-09-28 09:00 UTC>",
    ]


def test_view_command_for_an_unknown_handle_reports_no_rotation() -> None:
    reply = FakeSlackReply()
    payload = CommandPayload(text="", user_id="U1", platform_metadata={"trigger_id": "trigger"})

    response = handle_view_command(payload, {"usergroup_handle": "nobody"}, reply, _lookup(*_two_shifts()))

    assert response.message == "No user rotation configured for `nobody`."
    assert reply.calls == []


def test_view_command_reports_failure_when_the_modal_cannot_be_opened() -> None:
    reply = FakeSlackReply(OperationResult.error(OperationStatus.PERMANENT_ERROR, "expired", error_code="expired_trigger_id"))
    payload = CommandPayload(text="", user_id="U1", platform_metadata={"trigger_id": "trigger"})

    response = handle_view_command(payload, {"usergroup_handle": HANDLE}, reply, _lookup(*_two_shifts()))

    assert response.message == "Unable to open the user rotation view."
    assert response.ephemeral is True


def test_view_command_without_trigger_id_opens_nothing() -> None:
    reply = FakeSlackReply()
    payload = CommandPayload(text="", user_id="U1")

    response = handle_view_command(payload, {"usergroup_handle": HANDLE}, reply, _lookup(*_two_shifts()))

    assert response.message == "Unable to open the user rotation view."
    assert reply.calls == []
