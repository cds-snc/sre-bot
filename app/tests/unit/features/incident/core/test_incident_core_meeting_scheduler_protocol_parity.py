"""One behaviour suite for every MeetingScheduler and CalendarAvailability: the Google Calendar adapters and the fakes.

The adapters run over ``StubCalendar`` (conftest), which answers as Calendar
documents (client-supplied ids, 409 on a repeated id, a cancelled resource and
410 for deleted events, free/busy per calendar with errors); the fakes are
built with the same data. Each test runs against both, so a consumer tested on
a fake sees the adapter's observable rules. The adapters' blocking requests are
pinned to run off the event loop's thread.
"""

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from features.incident.core.adapters.google_calendar import GoogleCalendarAvailability, GoogleCalendarMeetingScheduler
from features.incident.core.adapters.in_memory import InMemoryCalendarAvailability, InMemoryMeetingScheduler
from features.incident.core.api import (
    BusyInterval,
    CalendarAvailability,
    MeetingChange,
    MeetingRequest,
    MeetingScheduler,
    MeetingStatus,
)
from tests.unit.features.incident.core.conftest import StubCalendar

pytestmark = pytest.mark.unit

START = datetime(2026, 12, 1, 15, 0, tzinfo=UTC)
END = START + timedelta(minutes=50)
BUSY_FROM = START - timedelta(hours=1)
BUSY_TO = START + timedelta(hours=1)


def _request(key: str = "incident-1:postmortem:1") -> MeetingRequest:
    return MeetingRequest(
        title="Postmortem",
        description="Review",
        start=START,
        end=END,
        time_zone="America/Toronto",
        attendees=("a@example.test", "b@example.test"),
        idempotency_key=key,
    )


def _adapter(stub: StubCalendar) -> MeetingScheduler:
    return GoogleCalendarMeetingScheduler("team@group.calendar.google.com")


def _fake(stub: StubCalendar) -> MeetingScheduler:
    return InMemoryMeetingScheduler()


@pytest.fixture(params=[_adapter, _fake], ids=["google_calendar", "in_memory"])
def scheduler(request: pytest.FixtureRequest, stub_calendar: StubCalendar) -> MeetingScheduler:
    build: Callable[[StubCalendar], MeetingScheduler] = request.param
    return build(stub_calendar)


def test_both_schedulers_satisfy_the_protocol(scheduler: MeetingScheduler) -> None:
    assert isinstance(scheduler, MeetingScheduler)


async def test_create_then_get_returns_the_booked_meeting(scheduler: MeetingScheduler) -> None:
    created = await scheduler.create(_request())
    assert created.data is not None

    read = await scheduler.get(created.data.id)

    assert read.status is OperationStatus.SUCCESS
    assert read.data is not None
    assert (read.data.title, read.data.start, read.data.end) == ("Postmortem", START, END)
    assert read.data.status is MeetingStatus.CONFIRMED
    assert read.data.attendees == ("a@example.test", "b@example.test")
    assert read.data.video_url is not None


async def test_the_meeting_id_depends_only_on_the_key(scheduler: MeetingScheduler) -> None:
    first = await scheduler.create(_request("key-1"))
    replay = await scheduler.create(_request("key-1"))
    other = await scheduler.create(_request("key-2"))

    assert first.data is not None and replay.data is not None and other.data is not None
    assert replay.data == first.data
    assert other.data.id != first.data.id


async def test_patch_applies_the_change(scheduler: MeetingScheduler) -> None:
    created = await scheduler.create(_request())
    assert created.data is not None
    moved = START + timedelta(days=1)

    patched = await scheduler.patch(
        created.data.id,
        MeetingChange(start=moved, end=moved + timedelta(hours=1), time_zone="UTC", attendees=("c@example.test",)),
    )
    read = await scheduler.get(created.data.id)

    assert patched.data is not None and read.data is not None
    assert (read.data.start, read.data.attendees) == (moved, ("c@example.test",))
    assert read.data.title == "Postmortem"


async def test_a_deleted_meeting_is_gone_and_its_key_cannot_book_again(scheduler: MeetingScheduler) -> None:
    created = await scheduler.create(_request())
    assert created.data is not None
    meeting_id = created.data.id

    assert (await scheduler.delete(meeting_id)).status is OperationStatus.SUCCESS
    assert (await scheduler.delete(meeting_id)).status is OperationStatus.SUCCESS
    gone = await scheduler.get(meeting_id)
    patched = await scheduler.patch(meeting_id, MeetingChange(title="x"))
    rebooked = await scheduler.create(_request())

    assert (gone.status, gone.error_code) == (OperationStatus.NOT_FOUND, ErrorCode.NOT_FOUND)
    assert patched.status is OperationStatus.NOT_FOUND
    assert (rebooked.status, rebooked.error_code) == (OperationStatus.PERMANENT_ERROR, "409")


async def test_an_unknown_meeting_is_not_found(scheduler: MeetingScheduler) -> None:
    assert (await scheduler.get("abcdefgh")).status is OperationStatus.NOT_FOUND
    assert (await scheduler.patch("abcdefgh", MeetingChange(title="x"))).status is OperationStatus.NOT_FOUND
    assert (await scheduler.delete("abcdefgh")).status is OperationStatus.NOT_FOUND


async def test_the_adapter_runs_its_requests_off_the_event_loop(stub_calendar: StubCalendar) -> None:
    scheduler = _adapter(stub_calendar)
    created = await scheduler.create(_request())
    assert created.data is not None
    await scheduler.get(created.data.id)
    await scheduler.patch(created.data.id, MeetingChange(title="x"))
    await scheduler.delete(created.data.id)
    await GoogleCalendarAvailability().busy_periods(["a@example.test"], START, END)

    assert {call.method for call in stub_calendar.calls} == {"insert", "get", "patch", "delete", "query"}
    assert threading.get_ident() not in {call.thread for call in stub_calendar.calls}


def _adapter_availability(stub: StubCalendar) -> CalendarAvailability:
    stub.busy["a@example.test"] = [(BUSY_FROM, BUSY_TO)]
    stub.calendar_errors["u@example.test"] = "notFound"
    return GoogleCalendarAvailability()


def _fake_availability(stub: StubCalendar) -> CalendarAvailability:
    return InMemoryCalendarAvailability(busy={"a@example.test": [BusyInterval(BUSY_FROM, BUSY_TO)]}, unknown={"u@example.test"})


@pytest.fixture(params=[_adapter_availability, _fake_availability], ids=["google_calendar", "in_memory"])
def availability(request: pytest.FixtureRequest, stub_calendar: StubCalendar) -> CalendarAvailability:
    build: Callable[[StubCalendar], CalendarAvailability] = request.param
    return build(stub_calendar)


def test_both_availabilities_satisfy_the_protocol(availability: CalendarAvailability) -> None:
    assert isinstance(availability, CalendarAvailability)


async def test_busy_free_and_unknown_are_three_answers_clipped_to_the_window(availability: CalendarAvailability) -> None:
    result = await availability.busy_periods(["A@example.test", "f@example.test", "u@example.test"], START, END)

    assert result.status is OperationStatus.SUCCESS
    assert result.data is not None
    assert result.data["a@example.test"].busy == (BusyInterval(START, END),)
    assert result.data["f@example.test"].busy == ()
    assert result.data["u@example.test"].busy is None


async def test_a_bad_window_is_refused(availability: CalendarAvailability) -> None:
    with pytest.raises(ValueError):
        await availability.busy_periods(["a@example.test"], END, START)
