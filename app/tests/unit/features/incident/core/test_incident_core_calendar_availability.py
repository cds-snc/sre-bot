"""Reading people's free/busy through the Google Calendar CalendarAvailability.

``StubCalendar`` (conftest) answers ``freebusy().query`` from busy intervals,
per-calendar errors and omitted addresses. Unknown and free are different
answers: a calendar that answers with errors, or is missing from the answer, is
``busy=None``, never an empty tuple; a whole-query failure is a classified
error, never "everyone free". Requests go in batches of Calendar's documented
50-calendar cap and keep the factory's SDK retries.
"""

from datetime import UTC, datetime, timedelta

import pytest
from googleapiclient.errors import HttpError

from contracts.operations.status import OperationStatus
from features.incident.core.adapters.google_calendar import GoogleCalendarAvailability
from features.incident.core.domain import BusyInterval
from tests.unit.features.incident.core.conftest import StubCalendar, google_http_error

pytestmark = pytest.mark.unit

START = datetime(2026, 12, 1, 13, 0, tzinfo=UTC)
END = START + timedelta(hours=8)


async def test_busy_intervals_are_parsed_as_aware_times(stub_calendar: StubCalendar) -> None:
    stub_calendar.busy["a@example.test"] = [(START + timedelta(hours=1), START + timedelta(hours=2))]

    result = await GoogleCalendarAvailability().busy_periods(["a@example.test", "b@example.test"], START, END)

    assert result.status is OperationStatus.SUCCESS
    assert result.data is not None
    assert result.data["a@example.test"].busy == (BusyInterval(START + timedelta(hours=1), START + timedelta(hours=2)),)
    assert result.data["b@example.test"].busy == ()
    (call,) = stub_calendar.calls_to("query")
    assert call.params["body"]["timeMin"] == START.isoformat()
    assert call.num_retries is None


async def test_answers_are_keyed_by_the_case_folded_address_once(stub_calendar: StubCalendar) -> None:
    result = await GoogleCalendarAvailability().busy_periods([" A@Example.test", "a@example.test", " "], START, END)

    assert result.data is not None and list(result.data) == ["a@example.test"]
    assert stub_calendar.calls_to("query")[0].params["body"]["items"] == [{"id": "a@example.test"}]


@pytest.mark.parametrize("reason", ["notFound", "internalError", "tooManyCalendarsRequested", "someFutureReason"])
async def test_a_calendar_answering_with_errors_is_unknown(stub_calendar: StubCalendar, reason: str) -> None:
    stub_calendar.calendar_errors["a@example.test"] = reason

    result = await GoogleCalendarAvailability().busy_periods(["a@example.test"], START, END)

    assert result.data is not None
    assert result.data["a@example.test"].busy is None
    assert result.data["a@example.test"].known is False


async def test_an_address_missing_from_the_answer_is_unknown(stub_calendar: StubCalendar) -> None:
    stub_calendar.omitted.add("a@example.test")

    result = await GoogleCalendarAvailability().busy_periods(["a@example.test"], START, END)

    assert result.data is not None and result.data["a@example.test"].busy is None


async def test_more_than_fifty_addresses_are_queried_in_batches_and_merged(stub_calendar: StubCalendar) -> None:
    emails = [f"person{n}@example.test" for n in range(51)]
    stub_calendar.busy["person50@example.test"] = [(START, START + timedelta(minutes=30))]

    result = await GoogleCalendarAvailability().busy_periods(emails, START, END)

    batches = [len(call.params["body"]["items"]) for call in stub_calendar.calls_to("query")]
    assert batches == [50, 1]
    assert result.data is not None and len(result.data) == 51
    assert result.data["person50@example.test"].busy == (BusyInterval(START, START + timedelta(minutes=30)),)


async def test_a_failed_query_is_classified_and_never_all_free(stub_calendar: StubCalendar) -> None:
    stub_calendar.fail["query"] = google_http_error(503)

    result = await GoogleCalendarAvailability().busy_periods(["a@example.test"], START, END)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert result.data is None


async def test_an_unclassified_status_propagates(stub_calendar: StubCalendar) -> None:
    stub_calendar.fail["query"] = google_http_error(400)

    with pytest.raises(HttpError):
        await GoogleCalendarAvailability().busy_periods(["a@example.test"], START, END)


async def test_no_address_is_an_empty_answer_without_a_request(stub_calendar: StubCalendar) -> None:
    result = await GoogleCalendarAvailability().busy_periods([], START, END)

    assert result.status is OperationStatus.SUCCESS and result.data == {}
    assert stub_calendar.calls == []


@pytest.mark.parametrize(("start", "end"), [(START.replace(tzinfo=None), END), (END, START)], ids=["naive", "reversed"])
async def test_a_bad_window_is_refused(stub_calendar: StubCalendar, start: datetime, end: datetime) -> None:
    with pytest.raises(ValueError):
        await GoogleCalendarAvailability().busy_periods(["a@example.test"], start, end)
