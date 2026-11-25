"""Reading a meeting's current state through the Google Calendar MeetingScheduler.

``StubCalendar`` (conftest) holds events booked through the adapter, and its
``transform`` and ``fail`` hooks stand in for hand edits on the shared calendar
and Calendar's error answers. The calendar owns the time, so ``get`` returns
the event as it stands; a deleted or cancelled event is one NOT_FOUND answer
whatever form Calendar gives it (404, 410, a cancelled resource), and an event
edited into an all-day event has no time to return. Reads keep the factory's
SDK retries.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.core.adapters.google_calendar import GoogleCalendarMeetingScheduler
from features.incident.core.domain import MeetingRequest, MeetingStatus
from tests.unit.features.incident.core.conftest import StubCalendar, google_http_error

pytestmark = pytest.mark.unit

START = datetime(2026, 12, 1, 15, 0, tzinfo=UTC)
END = START + timedelta(minutes=50)


async def _booked(scheduler: GoogleCalendarMeetingScheduler) -> str:
    request = MeetingRequest(
        title="Postmortem",
        description="",
        start=START,
        end=END,
        time_zone="America/Toronto",
        attendees=("a@example.test",),
        idempotency_key="incident-1:postmortem:1",
    )
    result = await scheduler.create(request)
    assert result.data is not None
    return result.data.id


@pytest.fixture
def scheduler(stub_calendar: StubCalendar) -> GoogleCalendarMeetingScheduler:
    return GoogleCalendarMeetingScheduler("team@group.calendar.google.com")


async def test_get_returns_the_event_as_it_stands(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    """A time moved by hand on the calendar is what get returns: the calendar owns the time."""
    meeting_id = await _booked(scheduler)
    moved = START + timedelta(days=1)
    stub_calendar.stored[meeting_id]["start"] = {"dateTime": moved.isoformat(), "timeZone": "America/Toronto"}
    stub_calendar.stored[meeting_id]["end"] = {
        "dateTime": (moved + timedelta(hours=1)).isoformat(),
        "timeZone": "America/Toronto",
    }

    result = await scheduler.get(meeting_id)

    assert result.status is OperationStatus.SUCCESS
    assert result.data is not None
    assert result.data.start == moved
    assert result.data.end == moved + timedelta(hours=1)
    assert stub_calendar.calls_to("get")[0].params == {"calendarId": "team@group.calendar.google.com", "eventId": meeting_id}


async def test_reads_keep_the_factory_retries(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    await scheduler.get(await _booked(scheduler))

    assert stub_calendar.calls_to("get")[0].num_retries is None


async def test_a_tentative_event_stays_tentative(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    meeting_id = await _booked(scheduler)
    stub_calendar.stored[meeting_id]["status"] = "tentative"

    result = await scheduler.get(meeting_id)

    assert result.data is not None and result.data.status is MeetingStatus.TENTATIVE


async def test_the_video_link_falls_back_to_the_conference_entry_point(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    meeting_id = await _booked(scheduler)
    event = stub_calendar.stored[meeting_id]
    event.pop("hangoutLink")
    event["conferenceData"] = {
        "entryPoints": [
            {"entryPointType": "phone", "uri": "tel:+1-555"},
            {"entryPointType": "video", "uri": "https://meet.google.com/x"},
        ]
    }

    result = await scheduler.get(meeting_id)

    assert result.data is not None and result.data.video_url == "https://meet.google.com/x"


async def test_a_pending_conference_has_no_video_link(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    meeting_id = await _booked(scheduler)
    stub_calendar.stored[meeting_id].pop("hangoutLink")

    result = await scheduler.get(meeting_id)

    assert result.data is not None and result.data.video_url is None


async def test_a_deleted_event_is_not_found(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    """Calendar answers a deleted event with a cancelled resource without times: the meeting is gone."""
    meeting_id = await _booked(scheduler)
    await scheduler.delete(meeting_id)

    result = await scheduler.get(meeting_id)

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_FOUND


@pytest.mark.parametrize("status", [404, 410])
async def test_a_missing_or_gone_event_is_not_found(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler, status: int
) -> None:
    stub_calendar.fail["get"] = google_http_error(status)

    result = await scheduler.get("abcdefgh")

    assert result.status is OperationStatus.NOT_FOUND


def _all_day(event: dict[str, Any]) -> dict[str, Any]:
    return {**event, "start": {"date": "2026-12-01"}, "end": {"date": "2026-12-02"}}


async def test_an_all_day_event_is_an_invalid_response(
    stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler
) -> None:
    """A hand edit into an all-day event leaves no time to return; it is not read as midnight."""
    meeting_id = await _booked(scheduler)
    stub_calendar.transform["get"] = _all_day

    result = await scheduler.get(meeting_id)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INVALID_RESPONSE


async def test_a_transient_failure_is_classified(stub_calendar: StubCalendar, scheduler: GoogleCalendarMeetingScheduler) -> None:
    stub_calendar.fail["get"] = google_http_error(500)

    result = await scheduler.get("abcdefgh")

    assert result.status is OperationStatus.TRANSIENT_ERROR
