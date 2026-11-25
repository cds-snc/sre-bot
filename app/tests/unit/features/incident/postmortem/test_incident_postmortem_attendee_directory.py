"""The attendee directory over the conversation's accounts, and the schedule refusing when it cannot read.

``ConversationAttendeeDirectory`` runs over the in-memory conversation seeded with
people, so the assertions read what the port answers: each account's email,
``None`` for an account without one. A failed directory read makes the schedule book
nothing (the in-memory directory is built to fail).
"""

from dataclasses import replace
from datetime import UTC, datetime, time, timedelta

import pytest

from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from features.incident.core.adapters.in_memory import (
    InMemoryCalendarAvailability,
    InMemoryIncidentConversation,
    InMemoryIncidentStore,
    InMemoryMeetingScheduler,
    SeededAccount,
)
from features.incident.postmortem.adapters.attendees import ConversationAttendeeDirectory
from features.incident.postmortem.adapters.in_memory import (
    InMemoryAttendeeDirectory,
    InMemoryHolidayCalendar,
    InMemoryPostmortemEventSink,
)
from features.incident.postmortem.domain import HolidayLookupFailure, SlotPolicy
from features.incident.postmortem.interfaces import AttendeeDirectory
from features.incident.postmortem.service.schedule import SchedulePorts, ScheduleRequest, schedule
from tests.factories.incident import GOOGLE_TENANT, incident_on, slack_conversation

pytestmark = pytest.mark.unit

CONVERSATION = slack_conversation("C0INC")


async def test_the_directory_answers_each_accounts_email_and_none_without_one() -> None:
    conversations = InMemoryIncidentConversation(
        open_ids=("C0INC",), people={"U0ADA": SeededAccount("ada@example.org"), "U0NOMAIL": SeededAccount(None)}
    )
    directory = ConversationAttendeeDirectory(conversations)

    found = await directory.emails_for(CONVERSATION, ["U0ADA", "U0NOMAIL"])

    assert isinstance(directory, AttendeeDirectory)
    assert dict(found.data or {}) == {"U0ADA": "ada@example.org", "U0NOMAIL": None}


async def test_a_failed_directory_read_books_nothing() -> None:
    incidents = InMemoryIncidentStore()
    incidents.seed(replace(incident_on("C0INC", "INC1"), incident_commander="U0IC"))
    scheduler = InMemoryMeetingScheduler()
    ports = SchedulePorts(
        incidents=incidents,
        conversations=InMemoryIncidentConversation(open_ids=("C0INC",)),
        scheduler=scheduler,
        availability=InMemoryCalendarAvailability(),
        holidays=InMemoryHolidayCalendar(),
        attendees=InMemoryAttendeeDirectory(fail_with=OperationResult.transient_error("slack down", "ratelimited")),
        events=InMemoryPostmortemEventSink(),
    )
    policy = SlotPolicy(
        time_zone="America/Toronto",
        window_start=time(13, 0),
        window_end=time(15, 0),
        weekdays=frozenset({1, 2, 3, 4, 5}),
        duration=timedelta(minutes=30),
        step=timedelta(minutes=30),
        search_days=5,
        optional_quorum_percent=50,
    )
    request = ScheduleRequest(
        user_id="U0ASKER", required=("U0IC",), optional=(), start_after_days=1, now=datetime(2026, 12, 1, 12, tzinfo=UTC)
    )

    result = await schedule(
        ports,
        CONVERSATION,
        request,
        policy=policy,
        holiday_failure=HolidayLookupFailure.PROCEED,
        texts=_NoTexts(),
        meeting_tenant=GOOGLE_TENANT,
    )

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert scheduler.requests == []


class _NoTexts:
    """Never called: the schedule stops before any wording is needed."""

    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"texts.{name} used")
