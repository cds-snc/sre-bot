"""Scheduling the postmortem meeting through the schedule service, over the in-memory fakes.

Every port is its in-memory fake (incident store, conversation, meeting scheduler,
calendar availability, holiday calendar, attendee directory, event sink), and the
wording is a stub that tags each text, so assertions read what was booked, written,
posted and sent, not catalogue wording. ``now`` is fixed on Tuesday 1 December
2026 and the search starts the next day, so the first candidate is 13:00 EST
(18:00Z) on 2 December. The assertions pin the order of writes (meeting, then
reference, then notice, then event), that an existing meeting is shown and never
booked again, that a meeting deleted outside the bot is recreated under a key
naming the deleted one, and the holiday failure policy.
"""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.languages import MultilingualText
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.google_calendar import meeting_event_id
from features.incident.core.adapters.in_memory import (
    InMemoryCalendarAvailability,
    InMemoryIncidentConversation,
    InMemoryIncidentStore,
    InMemoryMeetingScheduler,
    SeededAccount,
)
from features.incident.core.api import (
    BusyInterval,
    Incident,
    MeetingRequest,
    PostmortemMeetingReference,
    ReferenceKind,
    ReportReference,
    ScheduledMeeting,
)
from features.incident.core.domain import ResourceReference
from features.incident.postmortem.adapters.in_memory import (
    InMemoryAttendeeDirectory,
    InMemoryHolidayCalendar,
    InMemoryPostmortemEventSink,
)
from features.incident.postmortem.domain import HolidayLookupFailure, NoSlotReason, SlotPolicy
from features.incident.postmortem.service.schedule import (
    SchedulePorts,
    ScheduleRequest,
    ScheduleState,
    prepare_schedule,
    preview,
    schedule,
)
from tests.factories.incident import GOOGLE_TENANT, incident_on, slack_conversation

pytestmark = pytest.mark.unit

CHANNEL = "C0INC"
CONVERSATION = slack_conversation(CHANNEL)
NOW = datetime(2026, 12, 1, 12, 0, tzinfo=UTC)
FIRST_SLOT = datetime(2026, 12, 2, 18, 0, tzinfo=UTC)
EMAILS: dict[str, str | None] = {"U0IC": "ic@example.org", "U0OPS": "ops@example.org", "U0BO": "bo@example.org", "U0NOMAIL": None}
POLICY = SlotPolicy(
    time_zone="America/Toronto",
    window_start=time(13, 0),
    window_end=time(15, 0),
    weekdays=frozenset({1, 2, 3, 4, 5}),
    duration=timedelta(minutes=30),
    step=timedelta(minutes=30),
    search_days=10,
    optional_quorum_percent=50,
)
REPORT = ReportReference(system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="doc-1", url="https://docs.example/doc-1")


class StubTexts:
    """Tags each text so assertions read which one was used and with what."""

    def meeting_label(self) -> MultilingualText:
        return MultilingualText((("en-US", "Retro"), ("fr-FR", "Rétro")))

    def meeting_description(self, incident: Incident) -> MultilingualText:
        return MultilingualText((("en-US", f"about {incident.id}"),))

    def report_title(self) -> str:
        return "report"

    def scheduled_notice(self, meeting: ScheduledMeeting, *, recreated: bool, holidays_unavailable: bool) -> MultilingualText:
        return MultilingualText((("en-US", f"notice {meeting.id} recreated={recreated} holidays={not holidays_unavailable}"),))


class ConflictingStore(InMemoryIncidentStore):
    """A legacy record not at its end state: every reference write conflicts."""

    async def set_reference(
        self, incident_id: str, kind: ReferenceKind, reference: ResourceReference
    ) -> OperationResult[Incident]:
        return OperationResult.permanent_error("record not at end state", "INCIDENT_RECORD_CONFLICT")


def _incident(**fields: Any) -> Incident:
    return replace(incident_on(CHANNEL, "INC1"), incident_commander="U0IC", report=REPORT, **fields)


def _ports(
    incident: Incident | None = None,
    *,
    store: InMemoryIncidentStore | None = None,
    archived: bool = False,
    busy: Mapping[str, list[BusyInterval]] | None = None,
    availability: InMemoryCalendarAvailability | None = None,
    holidays: InMemoryHolidayCalendar | None = None,
) -> SchedulePorts:
    incidents = store if store is not None else InMemoryIncidentStore()
    if incident is not None:
        incidents.seed(incident)
    conversations = InMemoryIncidentConversation(
        tenant=CONVERSATION.tenant,
        open_ids=() if archived else (CHANNEL,),
        archived_ids=(CHANNEL,) if archived else (),
        members={CHANNEL: ("U0IC", "U0OPS", "U0BO", "U0BOT")},
        people={
            "U0IC": SeededAccount("ic@example.org"),
            "U0OPS": SeededAccount("ops@example.org"),
            "U0BO": SeededAccount("bo@example.org"),
            "U0BOT": SeededAccount(None, human=False),
        },
    )
    return SchedulePorts(
        incidents=incidents,
        conversations=conversations,
        scheduler=InMemoryMeetingScheduler(),
        availability=availability if availability is not None else InMemoryCalendarAvailability(busy=busy),
        holidays=holidays if holidays is not None else InMemoryHolidayCalendar(),
        attendees=InMemoryAttendeeDirectory(EMAILS),
        events=InMemoryPostmortemEventSink(),
    )


def _request(*, required: tuple[str, ...] = ("U0IC",), optional: tuple[str, ...] = ("U0BO",)) -> ScheduleRequest:
    return ScheduleRequest(user_id="U0ASKER", required=required, optional=optional, start_after_days=1, now=NOW)


async def _schedule(ports: SchedulePorts, request: ScheduleRequest | None = None, **options: Any) -> Any:
    return await schedule(
        ports,
        CONVERSATION,
        request or _request(),
        policy=POLICY,
        holiday_failure=options.get("holiday_failure", HolidayLookupFailure.PROCEED),
        texts=StubTexts(),
        meeting_tenant=GOOGLE_TENANT,
    )


def _scheduler(ports: SchedulePorts) -> InMemoryMeetingScheduler:
    assert isinstance(ports.scheduler, InMemoryMeetingScheduler)
    return ports.scheduler


def _posts(ports: SchedulePorts) -> tuple[str, ...]:
    assert isinstance(ports.conversations, InMemoryIncidentConversation)
    return tuple(ports.conversations.posts_in(CONVERSATION))


def _sent(ports: SchedulePorts) -> list[Any]:
    assert isinstance(ports.events, InMemoryPostmortemEventSink)
    return ports.events.sent


async def test_a_conversation_without_an_incident_books_nothing() -> None:
    ports = _ports()

    result = await _schedule(ports)

    assert result.status is OperationStatus.NOT_FOUND
    assert _scheduler(ports).requests == []


async def test_booking_creates_the_meeting_then_writes_the_reference_posts_the_notice_and_sends_one_event() -> None:
    ports = _ports(_incident())

    result = await _schedule(ports)

    assert result.is_success
    outcome = result.data
    assert outcome.state is ScheduleState.BOOKED
    (request,) = _scheduler(ports).requests
    assert isinstance(request, MeetingRequest)
    assert request.idempotency_key == "INC1:postmortem:first"
    assert request.title == "Incident INC1"
    assert request.label == StubTexts().meeting_label()
    assert request.attendees == ("ic@example.org", "bo@example.org")
    assert (request.start, request.end) == (FIRST_SLOT, FIRST_SLOT + timedelta(minutes=30))
    assert request.time_zone == "America/Toronto"
    assert [(attachment.title, attachment.url) for attachment in request.attachments] == [("report", REPORT.url)]
    meeting_id = meeting_event_id("INC1:postmortem:first")
    stored = (await ports.incidents.get("INC1")).data
    assert stored is not None
    assert stored.postmortem_meeting == PostmortemMeetingReference(
        system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id=meeting_id, url=outcome.meeting.url
    )
    assert _posts(ports) == (f"notice {meeting_id} recreated=False holidays=True",)
    (event,) = _sent(ports)
    assert (event.incident_id, event.conversation_id, event.user_id, event.meeting_id, event.at) == (
        "INC1",
        CHANNEL,
        "U0ASKER",
        meeting_id,
        NOW,
    )


async def test_an_account_without_an_email_is_not_invited_and_is_named() -> None:
    ports = _ports(_incident())

    result = await _schedule(ports, _request(required=("U0IC", "U0NOMAIL")))

    assert result.data.state is ScheduleState.BOOKED
    assert _scheduler(ports).requests[0].attendees == ("ic@example.org", "bo@example.org")
    assert [attendee.account_id for attendee in result.data.search.required_unknown] == ["U0NOMAIL"]


async def test_a_busy_required_attendee_moves_the_meeting_to_the_next_slot() -> None:
    ports = _ports(_incident(), busy={"ic@example.org": [BusyInterval(FIRST_SLOT, FIRST_SLOT + timedelta(minutes=30))]})

    result = await _schedule(ports)

    assert result.data.meeting.start == FIRST_SLOT + timedelta(minutes=30)


async def test_a_meeting_booked_before_its_reference_was_written_is_replayed_not_booked_twice() -> None:
    """A double submit, or a retry after a failed reference write, sends the same key and gets the same meeting."""
    ports = _ports(_incident())
    first = await _schedule(ports)
    ports.incidents.seed(_incident())  # the reference write lost

    again = await _schedule(ports)

    assert again.data.state is ScheduleState.BOOKED
    assert again.data.meeting.id == first.data.meeting.id
    assert len(_scheduler(ports).requests) == 1


async def test_an_existing_meeting_is_shown_and_nothing_is_booked_posted_or_sent() -> None:
    ports = _ports(_incident())
    booked = await _schedule(ports)
    posts, sent = len(_posts(ports)), len(_sent(ports))

    again = await _schedule(ports)

    assert again.data.state is ScheduleState.ALREADY_SCHEDULED
    assert again.data.meeting == booked.data.meeting
    assert len(_scheduler(ports).requests) == 1
    assert (len(_posts(ports)), len(_sent(ports))) == (posts, sent)


async def test_a_meeting_deleted_outside_the_bot_is_recreated_under_a_key_naming_the_deleted_one() -> None:
    ports = _ports(_incident())
    booked = await _schedule(ports)
    deleted_id = booked.data.meeting.id
    await ports.scheduler.delete(deleted_id)

    with capture_logs() as logs:
        again = await _schedule(ports)

    assert again.data.state is ScheduleState.RECREATED
    assert again.data.previous_meeting_id == deleted_id
    assert _scheduler(ports).requests[-1].idempotency_key == f"INC1:postmortem:after:{deleted_id}"
    new_id = meeting_event_id(f"INC1:postmortem:after:{deleted_id}")
    stored = (await ports.incidents.get("INC1")).data
    assert stored is not None and stored.postmortem_meeting is not None
    assert stored.postmortem_meeting.vendor_id == new_id
    assert _posts(ports)[-1] == f"notice {new_id} recreated=True holidays=True"
    assert [event.meeting_id for event in _sent(ports)] == [deleted_id, new_id]
    assert any(log["event"] == "postmortem_meeting_recreated" and log["log_level"] == "info" for log in logs)


async def test_a_failed_read_of_the_existing_meeting_books_nothing() -> None:
    ports = _ports(_incident())
    await _schedule(ports)
    _scheduler(ports).fail_on["get"] = OperationResult.transient_error("calendar down", "503")

    result = await _schedule(ports)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert len(_scheduler(ports).requests) == 1


async def test_a_holiday_failure_under_proceed_books_without_holidays_says_so_and_warns() -> None:
    holidays = InMemoryHolidayCalendar(fail_with=OperationResult.transient_error("holidays down", "503"))
    ports = _ports(_incident(), holidays=holidays)

    with capture_logs() as logs:
        result = await _schedule(ports, holiday_failure=HolidayLookupFailure.PROCEED)

    assert result.data.state is ScheduleState.BOOKED
    assert result.data.holidays_unavailable is True
    assert _posts(ports)[-1].endswith("holidays=False")
    assert any(log["event"] == "holiday_lookup_failed" and log["log_level"] == "warning" for log in logs)


async def test_a_holiday_failure_under_refuse_books_nothing_and_names_the_reason() -> None:
    holidays = InMemoryHolidayCalendar(fail_with=OperationResult.transient_error("holidays down", "503"))
    ports = _ports(_incident(), holidays=holidays)

    result = await _schedule(ports, holiday_failure=HolidayLookupFailure.REFUSE)

    assert result.data.state is ScheduleState.NO_SLOT
    assert result.data.reason is NoSlotReason.HOLIDAYS_UNAVAILABLE
    assert _scheduler(ports).requests == []


async def test_the_holiday_lookup_asks_for_every_year_the_search_spans() -> None:
    holidays = InMemoryHolidayCalendar()
    ports = _ports(_incident(), holidays=holidays)

    await _schedule(ports, ScheduleRequest(user_id="U0ASKER", required=("U0IC",), optional=(), start_after_days=28, now=NOW))

    assert holidays.asked == [frozenset({2026, 2027})]


async def test_a_failed_availability_read_books_nothing_never_everyone_free() -> None:
    availability = InMemoryCalendarAvailability(fail_with=OperationResult.transient_error("freebusy down", "503"))
    ports = _ports(_incident(), availability=availability)

    result = await _schedule(ports)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert _scheduler(ports).requests == []


async def test_no_slot_books_nothing_and_names_the_blocking_attendee() -> None:
    ports = _ports(_incident(), busy={"ic@example.org": [BusyInterval(NOW, NOW + timedelta(days=30))]})

    result = await _schedule(ports)

    assert result.data.state is ScheduleState.NO_SLOT
    assert result.data.reason is NoSlotReason.REQUIRED_ALWAYS_BUSY
    assert [attendee.account_id for attendee in result.data.search.blocking_required] == ["U0IC"]
    assert _scheduler(ports).requests == []
    assert _posts(ports) == ()


async def test_a_failed_create_writes_no_reference_posts_nothing_and_sends_nothing() -> None:
    ports = _ports(_incident())
    _scheduler(ports).fail_on["create"] = OperationResult.transient_error("calendar down", "503")

    result = await _schedule(ports)

    assert result.status is OperationStatus.TRANSIENT_ERROR
    stored = (await ports.incidents.get("INC1")).data
    assert stored is not None and stored.postmortem_meeting is None
    assert (_posts(ports), _sent(ports)) == ((), [])


async def test_a_reference_conflict_still_books_and_warns() -> None:
    ports = _ports(_incident(), store=ConflictingStore())

    with capture_logs() as logs:
        result = await _schedule(ports)

    assert result.data.state is ScheduleState.BOOKED
    assert len(_sent(ports)) == 1
    assert any(log["event"] == "postmortem_meeting_reference_failed" and log["log_level"] == "warning" for log in logs)


async def test_an_archived_conversation_gets_no_notice_and_the_meeting_is_still_booked() -> None:
    ports = _ports(_incident(), archived=True)

    result = await _schedule(ports)

    assert result.data.state is ScheduleState.BOOKED
    assert _posts(ports) == ()
    assert result.data.notice_posted is False


async def test_the_prefill_requires_the_role_holders_and_invites_the_other_members() -> None:
    ports = _ports(_incident(operations_lead="U0OPS", postmortem_owner="U0IC"))

    prefill = await prepare_schedule(ports.incidents, ports.conversations, CONVERSATION, opener="U0BO")

    assert prefill.is_success
    assert prefill.data.required == ("U0IC", "U0OPS")
    assert prefill.data.optional == ("U0BO",)


async def test_the_prefill_requires_the_opener_when_no_role_is_held() -> None:
    ports = _ports(replace(_incident(), incident_commander=None))

    prefill = await prepare_schedule(ports.incidents, ports.conversations, CONVERSATION, opener="U0BO")

    assert prefill.data.required == ("U0BO",)
    assert prefill.data.optional == ("U0IC", "U0OPS")


async def test_the_prefill_of_a_conversation_without_an_incident_is_not_found() -> None:
    ports = _ports()

    prefill = await prepare_schedule(ports.incidents, ports.conversations, CONVERSATION, opener="U0BO")

    assert prefill.status is OperationStatus.NOT_FOUND


async def test_the_preview_names_who_is_busy_at_every_candidate_and_whose_calendar_is_unknown() -> None:
    ports = _ports(_incident(), busy={"bo@example.org": [BusyInterval(NOW, NOW + timedelta(days=30))]})

    overview = await preview(
        ports, CONVERSATION, required=("U0IC", "U0NOMAIL"), optional=("U0BO",), policy=POLICY, now=NOW, start_after_days=1
    )

    assert overview.is_success
    assert [attendee.account_id for attendee in overview.data.always_busy] == ["U0BO"]
    assert [attendee.account_id for attendee in overview.data.unknown] == ["U0NOMAIL"]
