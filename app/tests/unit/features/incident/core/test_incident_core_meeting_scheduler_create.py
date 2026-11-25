"""Booking a meeting through the Google Calendar MeetingScheduler.

The Calendar gateway factory is replaced by ``StubCalendar`` (conftest), which
stores inserted events under their client-supplied id and answers a second
insert of that id with a 409, as Calendar does. The assertions read the event
body the adapter sent and the classified result it returned: the body carries
the description, one id source shared with the conference request, no reminder
override, and invitees who cannot modify the event or invite others; a replay
of the same key returns the booked meeting instead of a second event; expected
failures are classified results and an unclassified status propagates.
"""

import base64
import hashlib
import re
from datetime import UTC, datetime, timedelta

import pytest
from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.core.adapters.google_calendar import GoogleCalendarMeetingScheduler, meeting_event_id
from features.incident.core.domain import MeetingAttachment, MeetingRequest, MeetingStatus
from integrations.google_workspace.client import GoogleCredentialsRefused
from tests.unit.features.incident.core.conftest import StubCalendar, google_http_error

pytestmark = pytest.mark.unit

CALENDAR = "team-calendar@group.calendar.google.com"
START = datetime(2026, 12, 1, 15, 0, tzinfo=UTC)
END = START + timedelta(minutes=50)
KEY = "incident-1:postmortem:1"


def _request(**overrides: object) -> MeetingRequest:
    values: dict[str, object] = {
        "title": "Postmortem",
        "description": "Review of the incident",
        "start": START,
        "end": END,
        "time_zone": "America/Toronto",
        "attendees": (" a@example.test", "b@example.test", "A@example.test"),
        "idempotency_key": KEY,
    }
    values.update(overrides)
    return MeetingRequest(**values)  # type: ignore[arg-type]


def _scheduler() -> GoogleCalendarMeetingScheduler:
    return GoogleCalendarMeetingScheduler(CALENDAR)


def test_the_event_id_is_the_lower_case_base32hex_sha256_of_the_key() -> None:
    """The id is deterministic, within Calendar's a-v and 0-9 alphabet and 5-1024 length, and hides the raw key."""
    expected = base64.b32hexencode(hashlib.sha256(KEY.encode()).digest()).decode().rstrip("=").lower()

    event_id = meeting_event_id(KEY)

    assert event_id == expected
    assert re.fullmatch(r"[a-v0-9]{5,1024}", event_id)
    assert meeting_event_id("another key") != event_id


async def test_the_event_body_carries_description_one_id_source_and_locked_guests(stub_calendar: StubCalendar) -> None:
    result = await _scheduler().create(_request())

    assert result.status is OperationStatus.SUCCESS
    (call,) = stub_calendar.calls_to("insert")
    body = call.params["body"]
    event_id = meeting_event_id(KEY)
    assert call.params["calendarId"] == CALENDAR
    assert body["id"] == event_id
    assert body["conferenceData"]["createRequest"] == {
        "requestId": event_id,
        "conferenceSolutionKey": {"type": "hangoutsMeet"},
    }
    assert body["summary"] == "Postmortem"
    assert body["description"] == "Review of the incident"
    assert body["guestsCanModify"] is False
    assert body["guestsCanInviteOthers"] is False
    assert "reminders" not in body
    assert body["attendees"] == [{"email": "a@example.test"}, {"email": "b@example.test"}]
    assert body["start"] == {"dateTime": START.isoformat(), "timeZone": "America/Toronto"}
    assert body["end"] == {"dateTime": END.isoformat(), "timeZone": "America/Toronto"}
    assert "attachments" not in body
    assert call.params["sendUpdates"] == "all"
    assert call.params["conferenceDataVersion"] == 1


async def test_the_reminder_is_left_to_each_calendar_default(stub_calendar: StubCalendar) -> None:
    """Calendar applies an event's reminders to the authenticated user only, so none are sent."""
    await _scheduler().create(_request())

    assert "reminders" not in stub_calendar.calls_to("insert")[0].params["body"]


async def test_attachments_are_sent_as_file_links(stub_calendar: StubCalendar) -> None:
    attachment = MeetingAttachment(title="Incident report", url="https://docs.google.com/document/d/doc-1")

    await _scheduler().create(_request(attachments=(attachment,)))

    (call,) = stub_calendar.calls_to("insert")
    assert call.params["body"]["attachments"] == [{"fileUrl": attachment.url, "title": "Incident report"}]
    assert call.params["supportsAttachments"] is True


async def test_create_returns_the_booked_meeting(stub_calendar: StubCalendar) -> None:
    result = await _scheduler().create(_request())

    meeting = result.data
    assert meeting is not None
    assert meeting.id == meeting_event_id(KEY)
    assert (meeting.start, meeting.end) == (START, END)
    assert meeting.status is MeetingStatus.CONFIRMED
    assert meeting.url.startswith("https://calendar.google.com/")
    assert meeting.video_url is not None and meeting.video_url.startswith("https://meet.google.com/")
    assert meeting.attendees == ("a@example.test", "b@example.test")


async def test_create_keeps_the_factory_retries(stub_calendar: StubCalendar) -> None:
    """The client-supplied id makes a replayed insert a 409, so the insert keeps the SDK's backoff."""
    await _scheduler().create(_request())

    assert stub_calendar.calls_to("insert")[0].num_retries is None


async def test_a_replay_of_the_same_key_returns_the_booked_meeting(stub_calendar: StubCalendar) -> None:
    """A second create with the key (a retry after a lost answer) reads the event back: no second event."""
    first = await _scheduler().create(_request())
    second = await _scheduler().create(_request())

    assert second.status is OperationStatus.SUCCESS
    assert second.data == first.data
    assert len(stub_calendar.stored) == 1


async def test_a_replay_of_a_deleted_meeting_key_is_a_permanent_conflict(stub_calendar: StubCalendar) -> None:
    """A deleted event's id cannot be booked again: the caller needs a new key for a new booking."""
    first = await _scheduler().create(_request())
    assert first.data is not None
    await _scheduler().delete(first.data.id)

    result = await _scheduler().create(_request())

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == "409"


@pytest.mark.parametrize(
    ("failure", "status", "error_code", "retry_after"),
    [
        (google_http_error(429, retry_after="7"), OperationStatus.TRANSIENT_ERROR, "429", 7),
        (google_http_error(503), OperationStatus.TRANSIENT_ERROR, "503", None),
        (google_http_error(403), OperationStatus.UNAUTHORIZED, "403", None),
        (GoogleCredentialsRefused("unauthorized_client"), OperationStatus.UNAUTHORIZED, "unauthorized_client", None),
    ],
    ids=["rate_limited", "unavailable", "forbidden", "refused_credentials"],
)
async def test_expected_failures_are_classified(
    stub_calendar: StubCalendar, failure: Exception, status: OperationStatus, error_code: str, retry_after: int | None
) -> None:
    stub_calendar.fail["insert"] = failure

    result = await _scheduler().create(_request())

    assert result.status is status
    assert result.error_code == error_code
    assert result.retry_after == retry_after


async def test_an_unclassified_status_propagates(stub_calendar: StubCalendar) -> None:
    """A 400 is a bug in the request, not data: it is raised, as the classifier decides."""
    stub_calendar.fail["insert"] = google_http_error(400)

    with pytest.raises(HttpError):
        await _scheduler().create(_request())


async def test_a_response_without_a_timed_start_is_an_invalid_response(stub_calendar: StubCalendar) -> None:
    stub_calendar.transform["insert"] = lambda event: {key: value for key, value in event.items() if key != "start"}

    result = await _scheduler().create(_request())

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INVALID_RESPONSE
