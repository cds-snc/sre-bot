"""Google Calendar adapter of the incident core: the meeting scheduler and calendar availability.

``GoogleCalendarMeetingScheduler`` is the ``MeetingScheduler`` behind ``core.api``
for one calendar, and ``GoogleCalendarAvailability`` the ``CalendarAvailability``.
Both are async and run each blocking request through ``asyncio.to_thread``
(decisions/outbound-clients.md), and return classified results. A meeting's
event id is derived from the caller's idempotency key (``meeting_event_id``) and
reused as the conference request id, so a replayed insert is Calendar's 409 and
reads the booked event back; insert, get, delete and free/busy keep the
factory's SDK retries, and patch makes one attempt because a resent patch can
repeat its notification emails. No call takes a delegation subject.

``get_freebusy``, ``insert_event`` and ``generate_unique_id`` are the legacy
functions the legacy retro scheduling calls until its cutover deletes them.
"""

import asyncio
import base64
import hashlib
import random
import string
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

import structlog
from googleapiclient.errors import HttpError

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from features.incident.core.domain import (
    AttendeeBusy,
    BusyInterval,
    MeetingChange,
    MeetingRequest,
    MeetingStatus,
    ScheduledMeeting,
)
from integrations.google_workspace.client import GoogleCredentialsRefused, classify_google_error, get_calendar_service

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import Event, FreeBusyRequest  # pyright: ignore[reportMissingModuleSource]

logger = structlog.get_logger()
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
# Calendar's documented maximum of calendars per free/busy query; a vendor limit, not a policy.
FREEBUSY_MAX_CALENDARS = 50


def generate_unique_id() -> str:
    # Define the characters to use in the ID
    chars = string.ascii_lowercase + string.digits

    # Function to generate a segment of three characters
    def generate_segment():
        return "".join(random.choices(chars, k=3))  # noqa: S311 -- non-secret readable ID, not used for security tokens

    # Generate the three segments and join them with hyphens
    segments = [generate_segment() for _ in range(3)]
    unique_id = "-".join(segments)

    return unique_id


def get_freebusy(time_min, time_max, items, **kwargs):
    """Return the free/busy response for the requested calendars."""
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": items,
    }

    service = get_calendar_service(
        scopes=CALENDAR_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    try:
        return service.freebusy().query(body=cast("FreeBusyRequest", body)).execute()
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "google_api_request_failed",
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        raise


def insert_event(
    start,
    end,
    emails,
    title,
    calendar_id="primary",
    incident_document=None,
    **kwargs,
) -> dict:
    """Create a new calendar event and return the scheduled metadata."""
    time_zone = "America/New_York"

    body = {
        "start": {"dateTime": start, "timeZone": time_zone},
        "end": {"dateTime": end, "timeZone": time_zone},
        "attendees": [{"email": email.strip()} for email in emails],
        "summary": title,
        "guestsCanModify": True,
        "guestsCanInviteOthers": True,
        "conferenceData": {
            "createRequest": {
                "requestId": generate_unique_id(),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if incident_document:
        body["attachments"] = [
            {
                "fileUrl": f"https://docs.google.com/document/d/{incident_document}",
                "mimeType": "application/vnd.google-apps.document",
                "title": "Incident Document",
            }
        ]
    else:
        body.pop("attachments", None)

    service = get_calendar_service(
        scopes=CALENDAR_SCOPES,
        delegated_user_email=kwargs.pop("delegated_user_email", None),
    )
    try:
        # Not naturally idempotent: a retry can create a duplicate event and re-send
        # invitations, so retries stay off until a retries-disabled handle exists at construction.
        result = (
            service.events()
            .insert(
                calendarId=calendar_id,
                body=cast("Event", body),
                supportsAttachments=True,
                sendUpdates="all",
                conferenceDataVersion=1,
            )
            .execute(num_retries=0)
        )
    except HttpError as exc:
        status, error_code, retry_after = classify_google_error(exc)
        logger.warning(
            "google_api_request_failed",
            status=status.value,
            error_code=error_code,
            retry_after=retry_after,
        )
        raise

    htmllink = result.get("htmlLink")
    start_time = result.get("start").get("dateTime")
    datetime_obj = datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S%z")
    formatted_datetime = datetime_obj.strftime("%A, %B %d, %Y at %I:%M %p")
    event_info = f"Retro has been scheduled for {formatted_datetime} EDT. Check your calendar for more details."
    return {"event_link": htmllink, "event_info": event_info}


def meeting_event_id(idempotency_key: str) -> str:
    """Return the Calendar event id for a booking key: lower-case base32hex of its SHA-256.

    52 characters in a-v and 0-9, within Calendar's client-supplied id rules (5 to 1024
    characters, unique per calendar, deleted events included); the raw key is not sent.
    """
    digest = hashlib.sha256(idempotency_key.encode()).digest()
    return base64.b32hexencode(digest).decode().rstrip("=").lower()


def _http_status(exc: HttpError) -> int:
    return int(exc.resp.status)


def _failed[T](event: str, exc: HttpError | GoogleCredentialsRefused) -> OperationResult[T]:
    """Classify an expected failure into a result; an unclassified status propagates from the classifier."""
    status, error_code, retry_after = classify_google_error(exc)
    logger.warning(event, status=status.value, error_code=error_code, retry_after=retry_after)
    return OperationResult.error(status=status, message=str(exc), error_code=error_code, retry_after=retry_after)


def _not_found[T](meeting_id: str) -> OperationResult[T]:
    return OperationResult.error(
        status=OperationStatus.NOT_FOUND, message=f"meeting {meeting_id} is not on the calendar", error_code=ErrorCode.NOT_FOUND
    )


def _invalid[T](event: str, meeting_id: str | None, reason: str) -> OperationResult[T]:
    logger.warning(event, meeting_id=meeting_id, reason=reason)
    return OperationResult.permanent_error(f"Calendar answered with {reason}", ErrorCode.INVALID_RESPONSE)


def _event_time(value: datetime, time_zone: str) -> dict[str, str]:
    return {"dateTime": value.isoformat(), "timeZone": time_zone}


def _attendees(addresses: Sequence[str]) -> list[dict[str, str]]:
    return [{"email": address} for address in addresses]


def _event_body(request: MeetingRequest, event_id: str) -> dict[str, Any]:
    """The inserted event: invitees cannot modify it or invite others; reminders stay each calendar's default."""
    body: dict[str, Any] = {
        "id": event_id,
        "summary": request.title,
        "description": request.description,
        "start": _event_time(request.start, request.time_zone),
        "end": _event_time(request.end, request.time_zone),
        "attendees": _attendees(request.attendees),
        "guestsCanModify": False,
        "guestsCanInviteOthers": False,
        "conferenceData": {"createRequest": {"requestId": event_id, "conferenceSolutionKey": {"type": "hangoutsMeet"}}},
    }
    if request.attachments:
        body["attachments"] = [{"fileUrl": attachment.url, "title": attachment.title} for attachment in request.attachments]
    return body


def _change_body(change: MeetingChange) -> dict[str, Any]:
    """Only the fields the change sets; the attendee list is the full replacement (Calendar replaces arrays)."""
    body: dict[str, Any] = {}
    if change.title is not None:
        body["summary"] = change.title
    if change.description is not None:
        body["description"] = change.description
    if change.start is not None and change.end is not None and change.time_zone is not None:
        body["start"] = _event_time(change.start, change.time_zone)
        body["end"] = _event_time(change.end, change.time_zone)
    if change.attendees is not None:
        body["attendees"] = _attendees(change.attendees)
    return body


def _timed(value: object) -> datetime | None:
    """The aware ``dateTime`` of an event time, or ``None`` for an all-day or malformed one."""
    if not isinstance(value, Mapping):
        return None
    raw = value.get("dateTime")
    if not isinstance(raw, str):
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _video_url(payload: Mapping[str, Any]) -> str | None:
    link = payload.get("hangoutLink")
    if isinstance(link, str) and link:
        return link
    conference = payload.get("conferenceData")
    entry_points = conference.get("entryPoints", []) if isinstance(conference, Mapping) else []
    for entry in entry_points:
        if isinstance(entry, Mapping) and entry.get("entryPointType") == "video" and isinstance(entry.get("uri"), str):
            return cast("str", entry["uri"])
    return None


def _meeting(event: str, payload: Mapping[str, Any]) -> OperationResult[ScheduledMeeting]:
    """Map an event resource to the meeting it is now; cancelled is not found, all-day or incomplete is invalid."""
    meeting_id = payload.get("id")
    if not isinstance(meeting_id, str) or not meeting_id:
        return _invalid(event, None, "an event without an id")
    raw_status = payload.get("status", "confirmed")
    if raw_status == "cancelled":
        return _not_found(meeting_id)
    try:
        status = MeetingStatus(raw_status)
    except ValueError:
        return _invalid(event, meeting_id, "an unknown event status")
    start, end = _timed(payload.get("start")), _timed(payload.get("end"))
    if start is None or end is None:
        return _invalid(event, meeting_id, "an event without a start and end time")
    url = payload.get("htmlLink")
    if not isinstance(url, str) or not url:
        return _invalid(event, meeting_id, "an event without a link")
    attendees = tuple(
        attendee["email"]
        for attendee in payload.get("attendees", [])
        if isinstance(attendee, Mapping) and isinstance(attendee.get("email"), str)
    )
    title = payload.get("summary")
    return OperationResult.success(
        ScheduledMeeting(
            id=meeting_id,
            title=title if isinstance(title, str) else "",
            start=start,
            end=end,
            status=status,
            url=url,
            video_url=_video_url(payload),
            attendees=attendees,
        )
    )


class GoogleCalendarMeetingScheduler:
    """``MeetingScheduler`` on one Google calendar, the one the bot user owns (decisions/service-accounts.md rule 5).

    Every request is built on a fresh Calendar resource from the gateway factory and run
    off the event loop. See the module docstring for the retry and id rules.
    """

    def __init__(self, calendar_id: str) -> None:
        if not calendar_id.strip():
            raise ValueError("calendar_id must not be blank")
        self._calendar_id = calendar_id

    def _events(self) -> Any:
        return get_calendar_service(scopes=CALENDAR_SCOPES).events()

    async def create(self, request: MeetingRequest) -> OperationResult[ScheduledMeeting]:
        """Book the meeting; a replay of the key returns the booked meeting, a deleted one's key is a 409."""
        event_id = meeting_event_id(request.idempotency_key)
        body = _event_body(request, event_id)

        def insert() -> dict[str, Any]:
            return cast(
                "dict[str, Any]",
                self._events()
                .insert(
                    calendarId=self._calendar_id,
                    body=cast("Event", body),
                    supportsAttachments=True,
                    sendUpdates="all",
                    conferenceDataVersion=1,
                )
                .execute(),
            )

        try:
            payload = await asyncio.to_thread(insert)
        except HttpError as exc:
            if _http_status(exc) == 409:
                return await self._replayed(event_id)
            return _failed("incident_meeting_create_failed", exc)
        except GoogleCredentialsRefused as exc:
            return _failed("incident_meeting_create_failed", exc)
        return _meeting("incident_meeting_create_failed", payload)

    async def _replayed(self, event_id: str) -> OperationResult[ScheduledMeeting]:
        """The key booked an event before: return it, or a permanent 409 when it was deleted since."""
        existing = await self.get(event_id)
        if existing.status is OperationStatus.NOT_FOUND:
            logger.warning("incident_meeting_create_failed", meeting_id=event_id, reason="key_of_a_deleted_meeting")
            return OperationResult.permanent_error(f"meeting {event_id} was deleted; a new booking needs a new key", "409")
        return existing

    async def get(self, meeting_id: str) -> OperationResult[ScheduledMeeting]:
        """Return the meeting as the calendar holds it now; deleted or cancelled is NOT_FOUND."""

        def read() -> dict[str, Any]:
            return cast("dict[str, Any]", self._events().get(calendarId=self._calendar_id, eventId=meeting_id).execute())

        try:
            payload = await asyncio.to_thread(read)
        except HttpError as exc:
            if _http_status(exc) == 410:
                return _not_found(meeting_id)
            return _failed("incident_meeting_get_failed", exc)
        except GoogleCredentialsRefused as exc:
            return _failed("incident_meeting_get_failed", exc)
        return _meeting("incident_meeting_get_failed", payload)

    async def patch(self, meeting_id: str, change: MeetingChange) -> OperationResult[ScheduledMeeting]:
        """Change only the fields set, notifying the invitees; one attempt."""
        body = _change_body(change)

        def send() -> dict[str, Any]:
            return cast(
                "dict[str, Any]",
                self._events()
                .patch(calendarId=self._calendar_id, eventId=meeting_id, body=cast("Event", body), sendUpdates="all")
                .execute(num_retries=0),
            )

        try:
            payload = await asyncio.to_thread(send)
        except HttpError as exc:
            if _http_status(exc) == 410:
                return _not_found(meeting_id)
            return _failed("incident_meeting_patch_failed", exc)
        except GoogleCredentialsRefused as exc:
            return _failed("incident_meeting_patch_failed", exc)
        return _meeting("incident_meeting_patch_failed", payload)

    async def delete(self, meeting_id: str) -> OperationResult[None]:
        """Delete the meeting, notifying the invitees; an already deleted one (410) is done, an unknown one NOT_FOUND."""

        def remove() -> None:
            self._events().delete(calendarId=self._calendar_id, eventId=meeting_id, sendUpdates="all").execute()

        try:
            await asyncio.to_thread(remove)
        except HttpError as exc:
            if _http_status(exc) == 410:
                return OperationResult.success()
            return _failed("incident_meeting_delete_failed", exc)
        except GoogleCredentialsRefused as exc:
            return _failed("incident_meeting_delete_failed", exc)
        return OperationResult.success()


def _busy_intervals(entry: object) -> tuple[BusyInterval, ...] | None:
    """The busy intervals of one calendar's answer, or ``None`` when it carries errors or is malformed."""
    if not isinstance(entry, Mapping) or entry.get("errors"):
        return None
    intervals: list[BusyInterval] = []
    for period in entry.get("busy", []):
        if not isinstance(period, Mapping):
            return None
        try:
            start = datetime.fromisoformat(period["start"])
            end = datetime.fromisoformat(period["end"])
            intervals.append(BusyInterval(start=start, end=end))
        except KeyError, TypeError, ValueError:
            return None
    return tuple(intervals)


class GoogleCalendarAvailability:
    """``CalendarAvailability`` over Google free/busy: people's calendars are read for free/busy only.

    Requests go in batches of at most ``FREEBUSY_MAX_CALENDARS`` in one off-loop call; a
    calendar that answers with errors, or is missing from the answer, is unknown.
    """

    async def busy_periods(
        self, emails: Sequence[str], start: datetime, end: datetime
    ) -> OperationResult[Mapping[str, AttendeeBusy]]:
        """Return one answer per requested address (keyed by its case-folded spelling); a failed query is an error, never all free."""
        if start.utcoffset() is None or end.utcoffset() is None:
            raise ValueError("start and end must be timezone-aware")
        if end <= start:
            raise ValueError("end must be after start")
        keys = list(dict.fromkeys(email.strip().casefold() for email in emails if email.strip()))
        if not keys:
            return OperationResult.success({})
        batches = [keys[i : i + FREEBUSY_MAX_CALENDARS] for i in range(0, len(keys), FREEBUSY_MAX_CALENDARS)]

        def query_all() -> dict[str, Any]:
            service = get_calendar_service(scopes=CALENDAR_SCOPES)
            calendars: dict[str, Any] = {}
            for batch in batches:
                body = {"timeMin": start.isoformat(), "timeMax": end.isoformat(), "items": [{"id": key} for key in batch]}
                answer = service.freebusy().query(body=cast("FreeBusyRequest", body)).execute()
                for address, entry in (answer.get("calendars") or {}).items():
                    calendars[str(address).casefold()] = entry
            return calendars

        try:
            calendars = await asyncio.to_thread(query_all)
        except (HttpError, GoogleCredentialsRefused) as exc:
            return _failed("incident_calendar_availability_failed", exc)
        answers = {key: AttendeeBusy(email=key, busy=_busy_intervals(calendars.get(key))) for key in keys}
        unknown = sum(1 for answer in answers.values() if not answer.known)
        if unknown:
            logger.info("incident_calendar_availability_unknown", requested=len(keys), unknown=unknown)
        return OperationResult.success(answers)
