"""Interfaces of the incident postmortem subdomain.

``HolidayCalendar`` reads the observed federal holidays the postmortem meeting
search skips; ``adapters/canada_holidays.py`` is the Canada Holidays API one and
``adapters/in_memory.py`` the fake. ``AttendeeDirectory`` resolves attendee
emails (where the people capability's resolution plugs in),
``PostmortemEventSink`` receives the scheduled event, and ``ScheduleTexts`` gives
the schedule service its wording, rendered by the entry-point layer from the
catalogues.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol, runtime_checkable

from contracts.languages import MultilingualText
from contracts.operations.result import OperationResult
from features.incident.core.api import ConversationReference, Incident, ScheduledMeeting


@runtime_checkable
class HolidayCalendar(Protocol):
    """Interface reading observed federal holidays; it holds no policy on what a failure means.

    Async; platform failures are classified results, never exceptions, and never an
    empty set standing in for "unknown": whether a search goes on without holidays is
    the caller's decision.
    """

    async def observed_federal_holidays(self, years: Collection[int]) -> OperationResult[frozenset[date]]:
        """Return the observed dates of the federal holidays of every year in ``years``.

        A search window may cross a year end, so the caller names each year it spans.
        No year is an empty set.
        """
        ...


@runtime_checkable
class AttendeeDirectory(Protocol):
    """Interface resolving the accounts asked to a meeting to their calendar emails.

    An email is a lookup attribute, never a key (decisions/people-and-accounts.md).
    """

    async def emails_for(
        self, conversation: ConversationReference, account_ids: Sequence[str]
    ) -> OperationResult[Mapping[str, str | None]]:
        """Return each account's email; ``None`` for an account without one, which the search names."""
        ...


@dataclass(frozen=True)
class MeetingScheduledEvent:
    """A postmortem meeting booked or recreated: the minimal named fields (decisions/observability.md)."""

    incident_id: str
    conversation_id: str
    user_id: str
    meeting_id: str
    at: datetime


@runtime_checkable
class PostmortemEventSink(Protocol):
    """Interface receiving the postmortem's auditable events; a failed send is logged by the sink, never raised."""

    async def send_meeting_scheduled(self, event: MeetingScheduledEvent) -> None:
        """Send one event for a booked or recreated meeting."""
        ...


@runtime_checkable
class ScheduleTexts(Protocol):
    """The schedule service's wording, rendered by the caller from the catalogues (the service holds none).

    The meeting and the channel notice are shared, so each is in the instance languages
    (decisions/languages.md).
    """

    def meeting_label(self) -> MultilingualText:
        """The kind of meeting (Retro / Rétro), shown before the incident title."""
        ...

    def meeting_description(self, incident: Incident) -> MultilingualText:
        """The invitation body."""
        ...

    def report_title(self) -> str:
        """The incident report attachment's title."""
        ...

    def scheduled_notice(self, meeting: ScheduledMeeting, *, recreated: bool, holidays_unavailable: bool) -> MultilingualText:
        """The channel notice for a booked meeting; ``recreated`` when it replaces one deleted outside the bot."""
        ...
