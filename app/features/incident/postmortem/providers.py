"""Feature-local dependency wiring for the incident postmortem subdomain.

Resolves the ports the schedule service reads and writes through, so the entry
points (TASK-145.10.4) name one place to substitute them (decisions/testing.md,
provider substitution) and never import adapters.
"""

from features.incident.core.api import (
    CalendarAvailability,
    IncidentConversation,
    MeetingScheduler,
    build_meeting_scheduler,
    get_calendar_availability,
    get_incident_conversation,
)
from features.incident.postmortem.adapters.attendees import ConversationAttendeeDirectory
from features.incident.postmortem.adapters.canada_holidays import CanadaHolidaysCalendar
from features.incident.postmortem.adapters.sentinel import SentinelPostmortemEventSink
from features.incident.postmortem.domain import SlotPolicy
from features.incident.postmortem.interfaces import AttendeeDirectory, HolidayCalendar, PostmortemEventSink
from features.incident.postmortem.settings import get_incident_postmortem_settings


def incident_conversation() -> IncidentConversation:
    """Return the process-wide ``IncidentConversation``."""
    return get_incident_conversation()


def meeting_scheduler() -> MeetingScheduler:
    """Return the ``MeetingScheduler`` on the configured retro calendar.

    Raises:
        ValueError: INCIDENT_POSTMORTEM__CALENDAR_ID is blank.
    """
    return build_meeting_scheduler(get_incident_postmortem_settings().calendar_id)


def calendar_availability() -> CalendarAvailability:
    """Return the process-wide ``CalendarAvailability``."""
    return get_calendar_availability()


def holiday_calendar() -> HolidayCalendar:
    """Return the Canada Holidays ``HolidayCalendar`` on the configured vendor client."""
    return CanadaHolidaysCalendar()


def attendee_directory() -> AttendeeDirectory:
    """Return the attendee directory over the conversation's accounts (TASK-83.10 swaps it for the people capability)."""
    return ConversationAttendeeDirectory(get_incident_conversation())


def event_sink() -> PostmortemEventSink:
    """Return the sink the scheduled event is sent to (TODO(TASK-122): the audit capability's sink)."""
    return SentinelPostmortemEventSink()


def slot_policy() -> SlotPolicy:
    """Return the meeting search policy of the [incident_postmortem] settings."""
    return get_incident_postmortem_settings().slot_policy()
