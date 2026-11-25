"""In-memory incident postmortem adapters with the real implementations' observable rules.

``InMemoryHolidayCalendar``: the ``CanadaHolidaysCalendar`` rules (only the asked
years' dates, no year an empty set, a failure a result and never an empty set).
``InMemoryPostmortemEventSink`` records each event; ``InMemoryAttendeeDirectory``
answers seeded emails, ``None`` for an account without one.
"""

from collections.abc import Collection, Mapping, Sequence
from datetime import date

from contracts.operations.result import OperationResult
from features.incident.core.api import ConversationReference
from features.incident.postmortem.interfaces import (
    AttendeeDirectory,
    HolidayCalendar,
    MeetingScheduledEvent,
    PostmortemEventSink,
)


class InMemoryHolidayCalendar(HolidayCalendar):
    """Answer from the observed holiday dates it is built with; ``asked`` records each request's years.

    ``fail_with`` makes every read return that error result instead.
    """

    def __init__(self, holidays: Collection[date] = (), *, fail_with: OperationResult[frozenset[date]] | None = None) -> None:
        self._holidays = frozenset(holidays)
        self.fail_with = fail_with
        self.asked: list[frozenset[int]] = []

    async def observed_federal_holidays(self, years: Collection[int]) -> OperationResult[frozenset[date]]:
        """Return the stored dates falling in the asked years, or the configured failure."""
        asked = frozenset(years)
        self.asked.append(asked)
        if self.fail_with is not None and asked:
            return self.fail_with
        return OperationResult.success(frozenset(day for day in self._holidays if day.year in asked))


class InMemoryPostmortemEventSink(PostmortemEventSink):
    """Record each sent event in ``sent``."""

    def __init__(self) -> None:
        self.sent: list[MeetingScheduledEvent] = []

    async def send_meeting_scheduled(self, event: MeetingScheduledEvent) -> None:
        """Record the event."""
        self.sent.append(event)


class InMemoryAttendeeDirectory(AttendeeDirectory):
    """Answer from the account-to-email map it is built with; ``fail_with`` makes every read return that error."""

    def __init__(
        self,
        emails: Mapping[str, str | None] | None = None,
        *,
        fail_with: OperationResult[Mapping[str, str | None]] | None = None,
    ) -> None:
        self._emails = dict(emails or {})
        self.fail_with = fail_with

    async def emails_for(
        self, conversation: ConversationReference, account_ids: Sequence[str]
    ) -> OperationResult[Mapping[str, str | None]]:
        """Return each asked account's seeded email, ``None`` when it has none."""
        if self.fail_with is not None:
            return self.fail_with
        return OperationResult.success({account: self._emails.get(account) for account in account_ids})
