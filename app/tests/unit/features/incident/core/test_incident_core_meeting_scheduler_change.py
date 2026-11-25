"""Rescheduling and cancelling a meeting through the Google Calendar MeetingScheduler.

``StubCalendar`` (conftest) holds an event booked through the adapter and
records every request. ``patch`` sends only the fields the change sets (the
attendee list as a full replacement, since Calendar replaces arrays), notifies
the invitees and makes one attempt, because a resent patch can repeat the
notification emails. ``delete`` notifies the invitees, keeps the SDK's retries
and treats Calendar's 410 for an already deleted event as done.
"""

from datetime import UTC, datetime, timedelta

import pytest

from contracts.operations.status import OperationStatus
from features.incident.core.adapters.google_calendar import GoogleCalendarMeetingScheduler
from features.incident.core.domain import MeetingChange, MeetingRequest
from tests.unit.features.incident.core.conftest import StubCalendar, google_http_error

pytestmark = pytest.mark.unit

START = datetime(2026, 12, 1, 15, 0, tzinfo=UTC)
END = START + timedelta(minutes=50)


@pytest.fixture
def scheduler(stub_calendar: StubCalendar) -> GoogleCalendarMeetingScheduler:
    return GoogleCalendarMeetingScheduler("team@group.calendar.google.com")


async def _booked(scheduler: GoogleCalendarMeetingScheduler) -> str:
    request = MeetingRequest(
        title="Postmortem",
        description="Review",
        start=START,
        end=END,
        time_zone="America/Toronto",
        attendees=("a@example.test", "b@example.test"),
        idempotency_key="incident-1:postmortem:1",
    )
    result = await scheduler.create(request)
    assert result.data is not None
    return result.data.id


async def test_patch_sends_only_the_fields_set_with_one_attempt(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    meeting_id = await _booked(scheduler)
    moved = START + timedelta(days=2)

    result = await scheduler.patch(
        meeting_id, MeetingChange(start=moved, end=moved + timedelta(hours=1), time_zone="America/Halifax")
    )

    assert result.status is OperationStatus.SUCCESS
    assert result.data is not None and result.data.start == moved
    (call,) = stub_calendar.calls_to("patch")
    assert call.params["body"] == {
        "start": {"dateTime": moved.isoformat(), "timeZone": "America/Halifax"},
        "end": {"dateTime": (moved + timedelta(hours=1)).isoformat(), "timeZone": "America/Halifax"},
    }
    assert call.params["sendUpdates"] == "all"
    assert call.params["eventId"] == meeting_id
    assert call.num_retries == 0


async def test_patch_replaces_the_whole_attendee_list(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    """Calendar replaces arrays, so the change carries every invitee that stays."""
    meeting_id = await _booked(scheduler)

    result = await scheduler.patch(meeting_id, MeetingChange(attendees=("b@example.test", "c@example.test")))

    assert stub_calendar.calls_to("patch")[0].params["body"] == {
        "attendees": [{"email": "b@example.test"}, {"email": "c@example.test"}]
    }
    assert result.data is not None and result.data.attendees == ("b@example.test", "c@example.test")


async def test_patch_of_title_and_description(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    meeting_id = await _booked(scheduler)

    await scheduler.patch(meeting_id, MeetingChange(title="Follow-up", description=""))

    assert stub_calendar.calls_to("patch")[0].params["body"] == {"summary": "Follow-up", "description": ""}


@pytest.mark.parametrize("status", [404, 410])
async def test_patch_of_a_missing_or_deleted_event_is_not_found(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler, status: int
) -> None:
    stub_calendar.fail["patch"] = google_http_error(status)

    result = await scheduler.patch("abcdefgh", MeetingChange(title="x"))

    assert result.status is OperationStatus.NOT_FOUND


async def test_patch_failure_is_classified(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    stub_calendar.fail["patch"] = google_http_error(429, retry_after="3")

    result = await scheduler.patch("abcdefgh", MeetingChange(title="x"))

    assert (result.status, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, 3)


async def test_delete_notifies_and_keeps_the_factory_retries(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    meeting_id = await _booked(scheduler)

    result = await scheduler.delete(meeting_id)

    assert result.status is OperationStatus.SUCCESS
    (call,) = stub_calendar.calls_to("delete")
    assert call.params == {"calendarId": "team@group.calendar.google.com", "eventId": meeting_id, "sendUpdates": "all"}
    assert call.num_retries is None


async def test_deleting_an_already_deleted_event_succeeds(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    """A retried delete whose first attempt landed gets a 410: the meeting is gone, as asked."""
    meeting_id = await _booked(scheduler)
    await scheduler.delete(meeting_id)

    result = await scheduler.delete(meeting_id)

    assert result.status is OperationStatus.SUCCESS


async def test_deleting_an_unknown_event_is_not_found(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    result = await scheduler.delete("abcdefgh")

    assert result.status is OperationStatus.NOT_FOUND


async def test_delete_failure_is_classified(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    stub_calendar.fail["delete"] = google_http_error(403)

    result = await scheduler.delete("abcdefgh")

    assert result.status is OperationStatus.UNAUTHORIZED
