"""Validation rules of the meeting domain types the MeetingScheduler and CalendarAvailability ports carry.

Each type is built directly; the assertions read the normalised fields or the
ValueError raised, so a caller gets a refusal at construction rather than a
vendor 400 later. No stubs are needed: the types are pure.
"""

from datetime import UTC, datetime, timedelta

import pytest

from features.incident.core.domain import (
    AttendeeBusy,
    BusyInterval,
    MeetingAttachment,
    MeetingChange,
    MeetingRequest,
)

pytestmark = pytest.mark.unit

START = datetime(2026, 12, 1, 15, 0, tzinfo=UTC)
END = START + timedelta(minutes=50)


def _request(**overrides: object) -> MeetingRequest:
    values: dict[str, object] = {
        "title": "Postmortem",
        "description": "Review of the incident",
        "start": START,
        "end": END,
        "time_zone": "America/Toronto",
        "attendees": ("a@example.test",),
        "idempotency_key": "incident-1:postmortem:1",
    }
    values.update(overrides)
    return MeetingRequest(**values)  # type: ignore[arg-type]


def test_attendees_are_stripped_and_deduplicated_case_insensitively_in_order() -> None:
    """The first spelling of each address is kept, so a repeated invitee is invited once."""
    request = _request(attendees=(" A@example.test ", "b@example.test", "a@EXAMPLE.test"))

    assert request.attendees == ("A@example.test", "b@example.test")


@pytest.mark.parametrize("field", ["title", "time_zone", "idempotency_key"])
def test_blank_required_text_is_refused(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        _request(**{field: "  "})


def test_a_blank_attendee_address_is_refused() -> None:
    with pytest.raises(ValueError, match="attendee"):
        _request(attendees=("a@example.test", " "))


def test_naive_times_are_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _request(start=START.replace(tzinfo=None))


def test_an_end_not_after_the_start_is_refused() -> None:
    with pytest.raises(ValueError, match="end"):
        _request(end=START)


def test_an_unknown_time_zone_is_refused() -> None:
    with pytest.raises(ValueError, match="time_zone"):
        _request(time_zone="Mars/Olympus")


def test_attachments_default_to_none() -> None:
    assert _request().attachments == ()


def test_an_attachment_needs_a_title_and_a_link() -> None:
    with pytest.raises(ValueError, match="url"):
        MeetingAttachment(title="Report", url=" ")


def test_a_change_with_nothing_set_is_refused() -> None:
    with pytest.raises(ValueError, match="nothing"):
        MeetingChange()


@pytest.mark.parametrize(
    "partial",
    [{"start": START}, {"start": START, "end": END}, {"end": END, "time_zone": "UTC"}],
)
def test_a_change_moves_the_time_only_with_start_end_and_zone_together(partial: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="together"):
        MeetingChange(**partial)  # type: ignore[arg-type]


def test_a_time_change_keeps_the_request_rules() -> None:
    with pytest.raises(ValueError, match="end"):
        MeetingChange(start=END, end=START, time_zone="UTC")


def test_a_change_normalises_the_replacement_attendee_list() -> None:
    """Attendees in a change are the full replacement list, normalised like a request's."""
    change = MeetingChange(attendees=("a@example.test", "A@example.test "))

    assert change.attendees == ("a@example.test",)


def test_an_empty_attendee_list_is_a_change() -> None:
    """Removing every invitee is a real change, not an empty one."""
    assert MeetingChange(attendees=()).attendees == ()


def test_busy_intervals_are_timezone_aware() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        BusyInterval(start=START.replace(tzinfo=None), end=END)


def test_unknown_availability_is_none_and_not_an_empty_tuple() -> None:
    """Unknown and free are different answers: None is unknown, an empty tuple is free."""
    assert AttendeeBusy(email="a@example.test", busy=None).known is False
    assert AttendeeBusy(email="a@example.test", busy=()).known is True
