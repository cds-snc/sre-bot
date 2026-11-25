"""Schedule the postmortem meeting: one upcoming meeting per incident, on the first slot the rules allow.

``schedule`` serves the schedule view's submission. It finds the conversation's
incident (a refusal books nothing). An incident whose meeting is on the calendar is
shown that meeting and nothing is booked: this service never changes a meeting. A
meeting deleted outside the bot is recreated under a key naming
the deleted one. Otherwise the attendees' emails are resolved, the holidays of every
year the search spans are read (a failure proceeds without them or refuses, as the
setting says), the calendars are read once for the whole search, and the domain
picks the slot. The writes then run in a fixed order: the meeting (the commit
point), the incident's reference to it, the channel notice when the conversation is
writable, and one scheduled event. A failed reference write or notice is logged and
never undoes the booking: the next schedule replays the same key and gets the same
meeting back, then writes the reference again.

``prepare_schedule`` fills the view's two pickers, and ``preview`` names who cannot
be counted on before the person submits.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

import structlog

from contracts.operations import OperationResult
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.api import (
    AttendeeBusy,
    CalendarAvailability,
    ConversationReference,
    Incident,
    IncidentConversation,
    IncidentStore,
    MeetingAttachment,
    MeetingRequest,
    MeetingScheduler,
    PostmortemMeetingReference,
    ReferenceKind,
    ScheduledMeeting,
    conversation_is_writable,
    find_incident_for_conversation,
)
from features.incident.postmortem.domain import (
    Attendee,
    AttendeeOverview,
    HolidayLookupFailure,
    NoSlotReason,
    Slot,
    SlotPolicy,
    SlotSearch,
    attendee_list,
    attendee_overview,
    candidate_slots,
    find_slot,
    search_start_date,
    search_years,
)
from features.incident.postmortem.interfaces import (
    AttendeeDirectory,
    HolidayCalendar,
    MeetingScheduledEvent,
    PostmortemEventSink,
    ScheduleTexts,
)

logger = structlog.get_logger()


class ScheduleState(StrEnum):
    """What a schedule did."""

    BOOKED = "booked"
    RECREATED = "recreated"
    ALREADY_SCHEDULED = "already_scheduled"
    NO_SLOT = "no_slot"


@dataclass(frozen=True)
class SchedulePorts:
    """The ports a schedule reads and writes through."""

    incidents: IncidentStore
    conversations: IncidentConversation
    scheduler: MeetingScheduler
    availability: CalendarAvailability
    holidays: HolidayCalendar
    attendees: AttendeeDirectory
    events: PostmortemEventSink


@dataclass(frozen=True)
class ScheduleRequest:
    """The schedule view's submission: who asked, the two attendee sets and when the search starts."""

    user_id: str
    required: tuple[str, ...]
    optional: tuple[str, ...]
    start_after_days: int
    now: datetime


@dataclass(frozen=True)
class ScheduleOutcome:
    """A schedule's outcome: the meeting (booked, recreated or existing) or why there is none.

    Attributes:
        state: What the schedule did.
        meeting: The meeting booked, recreated or found; ``None`` with no slot.
        search: The slot search with the people to name; ``None`` for an existing meeting.
        reason: Why nothing was booked, with ``NO_SLOT``.
        holidays_unavailable: The search ran without holidays because they could not be read.
        previous_meeting_id: The meeting deleted outside the bot that a recreated one replaces.
        notice_posted: Whether the channel notice was posted.
    """

    state: ScheduleState
    meeting: ScheduledMeeting | None = None
    search: SlotSearch | None = None
    reason: NoSlotReason | None = None
    holidays_unavailable: bool = False
    previous_meeting_id: str | None = None
    notice_posted: bool = False


@dataclass(frozen=True)
class SchedulePrefill:
    """The schedule view's defaults: the incident, the required and the optional attendees."""

    incident: Incident
    required: tuple[str, ...]
    optional: tuple[str, ...]


def first_key(incident_id: str) -> str:
    """The booking key of an incident's first meeting."""
    return f"{incident_id}:postmortem:first"


def recreated_key(incident_id: str, deleted_meeting_id: str) -> str:
    """The booking key of the meeting replacing ``deleted_meeting_id``: stable across retries, new per deletion."""
    return f"{incident_id}:postmortem:after:{deleted_meeting_id}"


async def prepare_schedule(
    incidents: IncidentStore, conversations: IncidentConversation, conversation: ConversationReference, *, opener: str
) -> OperationResult[SchedulePrefill]:
    """Default the required attendees to the incident's role holders (or ``opener``) and the optional to the other members.

    A conversation without an incident is the store's refusal. Members that cannot be
    read leave the optional set empty, logged at warning: the picker still works.
    """
    found = await find_incident_for_conversation(incidents, conversation)
    if not found.is_success or found.data is None:
        return _failure(found)
    incident = found.data
    holders = (incident.incident_commander, incident.operations_lead, incident.postmortem_owner)
    required = tuple(dict.fromkeys(holder for holder in holders if holder)) or (opener,)
    members = await conversations.members(conversation)
    if not members.is_success or members.data is None:
        logger.warning("postmortem_members_unreadable", incident_id=incident.id, error_code=members.error_code)
    optional = tuple(member for member in members.data or () if member not in required)
    return OperationResult.success(SchedulePrefill(incident=incident, required=required, optional=optional))


async def preview(
    ports: SchedulePorts,
    conversation: ConversationReference,
    *,
    required: tuple[str, ...],
    optional: tuple[str, ...],
    policy: SlotPolicy,
    now: datetime,
    start_after_days: int,
) -> OperationResult[AttendeeOverview]:
    """Name who is busy at every candidate and whose calendar is unknown, before the person submits.

    Holidays are not read: the warning is about people, and a holiday removes a day for everyone.
    """
    attendees = await _attendees(ports, conversation, required, optional)
    if isinstance(attendees, OperationResult):
        return _failure(attendees)
    candidates = candidate_slots(policy, search_start_date(policy, now, start_after_days), frozenset(), now=now)
    busy = await _busy(ports, attendees, candidates)
    if not busy.is_success or busy.data is None:
        return _failure(busy)
    return OperationResult.success(attendee_overview(attendees, busy.data, candidates))


async def schedule(
    ports: SchedulePorts,
    conversation: ConversationReference,
    request: ScheduleRequest,
    *,
    policy: SlotPolicy,
    holiday_failure: HolidayLookupFailure,
    texts: ScheduleTexts,
    meeting_tenant: str,
) -> OperationResult[ScheduleOutcome]:
    """Book the incident's postmortem meeting, show the existing one, or say why there is none.

    Args:
        ports: The ports read and written.
        conversation: The incident's conversation the view was opened from.
        request: The submission.
        policy: The search policy ([incident_postmortem] settings).
        holiday_failure: What a failed holiday read does.
        texts: The meeting's and the notice's wording.
        meeting_tenant: The calendar system's tenant, stored in the meeting reference.

    Returns:
        The outcome; the store's refusal, a failed meeting or calendar read, or a failed
        booking as their classified results, with nothing written.
    """
    found = await find_incident_for_conversation(ports.incidents, conversation)
    if not found.is_success or found.data is None:
        return _failure(found)
    incident = found.data

    key = first_key(incident.id)
    previous: str | None = None
    if incident.postmortem_meeting is not None:
        existing = await ports.scheduler.get(incident.postmortem_meeting.vendor_id)
        if existing.is_success and existing.data is not None:
            return OperationResult.success(ScheduleOutcome(state=ScheduleState.ALREADY_SCHEDULED, meeting=existing.data))
        if existing.status is not OperationStatus.NOT_FOUND:
            return _failure(existing)
        previous = incident.postmortem_meeting.vendor_id
        key = recreated_key(incident.id, previous)

    attendees = await _attendees(ports, conversation, request.required, request.optional)
    if isinstance(attendees, OperationResult):
        return _failure(attendees)

    first = search_start_date(policy, request.now, request.start_after_days)
    holidays = await _holidays(ports, incident, policy, first)
    holidays_unavailable = holidays is None
    if holidays is None and holiday_failure is HolidayLookupFailure.REFUSE:
        return OperationResult.success(
            ScheduleOutcome(state=ScheduleState.NO_SLOT, reason=NoSlotReason.HOLIDAYS_UNAVAILABLE, holidays_unavailable=True)
        )
    candidates = candidate_slots(policy, first, holidays or frozenset(), now=request.now)
    busy = await _busy(ports, attendees, candidates)
    if not busy.is_success or busy.data is None:
        return _failure(busy)
    search = find_slot(policy, attendees, busy.data, candidates)
    if search.slot is None:
        return OperationResult.success(
            ScheduleOutcome(
                state=ScheduleState.NO_SLOT, search=search, reason=search.reason, holidays_unavailable=holidays_unavailable
            )
        )

    booked = await ports.scheduler.create(_meeting_request(incident, attendees, search.slot, policy, texts, key))
    if not booked.is_success or booked.data is None:
        return _failure(booked)
    meeting = booked.data

    await _write_reference(ports, incident, meeting, meeting_tenant)
    recreated = previous is not None
    notice_posted = await _post_notice(ports, incident, conversation, texts, meeting, recreated, holidays_unavailable)
    await ports.events.send_meeting_scheduled(
        MeetingScheduledEvent(
            incident_id=incident.id,
            conversation_id=conversation.vendor_id,
            user_id=request.user_id,
            meeting_id=meeting.id,
            at=request.now,
        )
    )
    if recreated:
        logger.info("postmortem_meeting_recreated", incident_id=incident.id, meeting_id=meeting.id, previous_meeting_id=previous)
    else:
        logger.info("postmortem_meeting_booked", incident_id=incident.id, meeting_id=meeting.id)
    return OperationResult.success(
        ScheduleOutcome(
            state=ScheduleState.RECREATED if recreated else ScheduleState.BOOKED,
            meeting=meeting,
            search=search,
            holidays_unavailable=holidays_unavailable,
            previous_meeting_id=previous,
            notice_posted=notice_posted,
        )
    )


async def _attendees(
    ports: SchedulePorts, conversation: ConversationReference, required: tuple[str, ...], optional: tuple[str, ...]
) -> tuple[Attendee, ...] | OperationResult[Mapping[str, str | None]]:
    """The attendees with their emails, or the directory's failed read."""
    accounts = tuple(dict.fromkeys(required + optional))
    emails = await ports.attendees.emails_for(conversation, accounts)
    if not emails.is_success or emails.data is None:
        return emails
    return attendee_list(required=required, optional=optional, emails=emails.data)


async def _holidays(ports: SchedulePorts, incident: Incident, policy: SlotPolicy, first: date) -> frozenset[date] | None:
    """The observed holidays of every year the search spans; ``None`` when they could not be read (logged at warning)."""
    read = await ports.holidays.observed_federal_holidays(search_years(policy, first))
    if read.is_success and read.data is not None:
        return read.data
    logger.warning("holiday_lookup_failed", incident_id=incident.id, error_code=read.error_code)
    return None


async def _busy(
    ports: SchedulePorts, attendees: tuple[Attendee, ...], candidates: tuple[Slot, ...]
) -> OperationResult[Mapping[str, AttendeeBusy]]:
    """One availability read for the whole search; nobody to read (or no candidate) is an empty answer without a call."""
    emails = tuple(attendee.email for attendee in attendees if attendee.email)
    if not emails or not candidates:
        return OperationResult.success({})
    return await ports.availability.busy_periods(emails, candidates[0].start, candidates[-1].end)


def _meeting_request(
    incident: Incident, attendees: tuple[Attendee, ...], slot: Slot, policy: SlotPolicy, texts: ScheduleTexts, key: str
) -> MeetingRequest:
    report_url = incident.report.url if incident.report is not None else None
    return MeetingRequest(
        title=incident.title,
        label=texts.meeting_label(),
        description=texts.meeting_description(incident),
        start=slot.start,
        end=slot.end,
        time_zone=policy.time_zone,
        attendees=tuple(attendee.email for attendee in attendees if attendee.email),
        idempotency_key=key,
        attachments=(MeetingAttachment(title=texts.report_title(), url=report_url),) if report_url else (),
    )


async def _write_reference(ports: SchedulePorts, incident: Incident, meeting: ScheduledMeeting, tenant: str) -> None:
    reference = PostmortemMeetingReference(system=WorkplaceSystem.GOOGLE, tenant=tenant, vendor_id=meeting.id, url=meeting.url)
    written = await ports.incidents.set_reference(incident.id, ReferenceKind.POSTMORTEM_MEETING, reference)
    if not written.is_success:
        logger.warning(
            "postmortem_meeting_reference_failed", incident_id=incident.id, meeting_id=meeting.id, error_code=written.error_code
        )


async def _post_notice(
    ports: SchedulePorts,
    incident: Incident,
    conversation: ConversationReference,
    texts: ScheduleTexts,
    meeting: ScheduledMeeting,
    recreated: bool,
    holidays_unavailable: bool,
) -> bool:
    writable = await conversation_is_writable(ports.conversations, conversation)
    if not writable.is_success or not writable.data:
        logger.info("postmortem_notice_skipped", incident_id=incident.id, error_code=writable.error_code)
        return False
    notice = texts.scheduled_notice(meeting, recreated=recreated, holidays_unavailable=holidays_unavailable)
    posted = await ports.conversations.post(conversation, notice)
    if not posted.is_success:
        logger.warning("postmortem_notice_failed", incident_id=incident.id, error_code=posted.error_code)
    return posted.is_success


def _failure[T](result: OperationResult[Any]) -> OperationResult[T]:
    return OperationResult.error(
        status=result.status, message=result.message or "", error_code=result.error_code, retry_after=result.retry_after
    )
