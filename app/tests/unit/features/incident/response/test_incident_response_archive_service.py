"""``archive_incident``: find, join, close through ``change_status``, the archived notice, archive, then one event.

Runs over the core in-memory fakes (incident store, report, list projection and
conversation), which the core parity suites hold to the adapters' rules, and a
recording event sink; a test-local subclass fails one port. Assertions read the
fakes back in domain terms (the stored status, the channel's posts, whether the
channel is archived, the events sent) and the stage outcomes the service returns,
since the entry points render their replies from those outcomes.

The record is the commit point (decisions/incident-management.md): a refused
command check or a failed record write writes nothing else and sends no event. A
failed join is a conversation failure, so the record still closes and the notice
and the archive are skipped (TASK-145.8.5.3 OQ4). The event is sent once, only
after a successful archive (TASK-145.8.5 OQ8).
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Self

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
    InMemoryIncidentStore,
)
from features.incident.core.api import ConversationReference, Incident, ReportReference
from features.incident.response.interfaces import ArchivedEvent
from features.incident.response.service.archive import Archive, archive_incident
from features.incident.response.service.status import StageOutcome
from tests.factories.incident import GOOGLE_TENANT, incident_on, slack_conversation

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
INCIDENT_ID = "inc-1"
USER_ID = "U0PRESSER"
AT = datetime(2026, 11, 17, 15, 0, tzinfo=UTC)
STATUS_NOTICE = f"<@{USER_ID}> has updated the incident status to Closed."
ARCHIVED_NOTICE = f"<@{USER_ID}> has archived this channel 👋"


class RecordingSink:
    """Records each archived event it is sent."""

    def __init__(self) -> None:
        self.sent: list[ArchivedEvent] = []

    async def send_channel_archived(self, event: ArchivedEvent) -> None:
        self.sent.append(event)


class _Ports:
    """The ports over in-memory fakes, the incident seeded with its report; the channel state is the test's."""

    def __init__(
        self, reports: InMemoryIncidentReport, report: ReportReference, conversations: InMemoryIncidentConversation
    ) -> None:
        self.reports = reports
        self.incidents = InMemoryIncidentStore()
        self.incidents.seed(replace(incident_on(CHANNEL_ID, INCIDENT_ID), report=report))
        self.projection = InMemoryIncidentListProjection()
        self.conversations = conversations
        self.events = RecordingSink()

    @classmethod
    async def seeded(cls, conversations: InMemoryIncidentConversation | None = None) -> Self:
        reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0", next_ids=["D0"])
        created = await reports.create_from_template("Incident")
        assert created.data is not None
        return cls(reports, created.data, conversations or InMemoryIncidentConversation(open_ids=[CHANNEL_ID]))

    async def archive(self, conversation: ConversationReference | None = None) -> OperationResult[Archive]:
        return await archive_incident(
            self.incidents,
            self.reports,
            self.projection,
            self.conversations,
            self.events,
            conversation or slack_conversation(CHANNEL_ID),
            user_id=USER_ID,
            at=AT,
            status_notice=STATUS_NOTICE,
            archived_notice=ARCHIVED_NOTICE,
        )

    async def stored_status(self) -> IncidentStatus:
        found = await self.incidents.get(INCIDENT_ID)
        assert found.data is not None
        return found.data.status

    def posts(self) -> tuple[str, ...]:
        return tuple(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))

    def archived(self) -> bool:
        return self.conversations.is_archived(slack_conversation(CHANNEL_ID))


def _done(result: OperationResult[Archive]) -> Archive:
    assert result.is_success and result.data is not None, result
    return result.data


async def test_an_archive_closes_the_incident_announces_it_archives_the_channel_and_sends_one_event() -> None:
    ports = await _Ports.seeded()

    archive = _done(await ports.archive())

    assert await ports.stored_status() is IncidentStatus.CLOSED
    assert ports.posts() == (STATUS_NOTICE, ARCHIVED_NOTICE)
    assert ports.archived()
    assert ports.events.sent == [ArchivedEvent(incident_id=INCIDENT_ID, conversation_id=CHANNEL_ID, user_id=USER_ID, at=AT)]
    assert (archive.join.outcome, archive.notice.outcome, archive.archive.outcome) == (StageOutcome.DONE,) * 3
    assert archive.change.incident.status is IncidentStatus.CLOSED


async def test_a_channel_the_bot_left_is_joined_before_anything_is_posted() -> None:
    conversations = InMemoryIncidentConversation(non_member_ids=[CHANNEL_ID])
    ports = await _Ports.seeded(conversations)

    _done(await ports.archive())

    assert conversations.joined == [slack_conversation(CHANNEL_ID)]
    assert ports.posts() == (STATUS_NOTICE, ARCHIVED_NOTICE)
    assert ports.archived()


async def test_a_conversation_of_no_incident_is_refused_with_nothing_written_and_no_event() -> None:
    ports = await _Ports.seeded(InMemoryIncidentConversation(open_ids=[CHANNEL_ID, "C0OTHER"]))

    result = await ports.archive(slack_conversation("C0OTHER"))

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT
    assert await ports.stored_status() is IncidentStatus.OPEN
    assert ports.conversations.posts_in(slack_conversation("C0OTHER")) == ()
    assert not ports.conversations.is_archived(slack_conversation("C0OTHER"))
    assert ports.conversations.joined == []
    assert ports.events.sent == []


async def test_a_failed_record_write_stops_before_any_post_the_archive_and_the_event() -> None:
    class FailingStore(InMemoryIncidentStore):
        async def set_status(self, incident_id: str, status: IncidentStatus, *, at: datetime) -> OperationResult[Incident]:
            return OperationResult.transient_error("table down")

    ports = await _Ports.seeded()
    failing = FailingStore()
    failing.seed(replace(incident_on(CHANNEL_ID, INCIDENT_ID)))
    ports.incidents = failing

    result = await ports.archive()

    assert result.status is OperationStatus.TRANSIENT_ERROR
    assert ports.posts() == ()
    assert not ports.archived()
    assert ports.events.sent == []


async def test_a_failed_join_still_closes_the_record_and_skips_the_notice_the_archive_and_the_event() -> None:
    conversations = InMemoryIncidentConversation(private_non_member_ids=[CHANNEL_ID])
    ports = await _Ports.seeded(conversations)

    archive = _done(await ports.archive())

    assert await ports.stored_status() is IncidentStatus.CLOSED
    assert archive.join.outcome is StageOutcome.FAILED
    assert archive.join.error_code == ErrorCode.CONVERSATION_NOT_WRITABLE
    assert archive.change.channel.outcome is StageOutcome.SKIPPED
    assert (archive.notice.outcome, archive.archive.outcome) == (StageOutcome.SKIPPED, StageOutcome.SKIPPED)
    assert (archive.notice.reason, archive.archive.reason) == ("not_joined", "not_joined")
    assert not ports.archived()
    assert ports.events.sent == []


async def test_a_failed_follower_is_reported_and_the_channel_is_still_archived() -> None:
    ports = await _Ports.seeded()
    ports.projection = InMemoryIncidentListProjection(
        fail_with=OperationResult.permanent_error("no sheet", ErrorCode.CONFIG_NOT_CONFIGURED)
    )

    archive = _done(await ports.archive())

    assert archive.change.projection.outcome is StageOutcome.FAILED
    assert ports.archived()
    assert len(ports.events.sent) == 1


async def test_a_failed_archived_notice_is_reported_and_the_channel_is_still_archived() -> None:
    class NoticeRefused(InMemoryIncidentConversation):
        async def post(self, conversation: ConversationReference, text: str, **kwargs: object) -> OperationResult:  # type: ignore[override]
            if text == ARCHIVED_NOTICE:
                return OperationResult.transient_error("rate limited", "ratelimited")
            return await super().post(conversation, text)

    ports = await _Ports.seeded(NoticeRefused(open_ids=[CHANNEL_ID]))

    archive = _done(await ports.archive())

    assert archive.notice.outcome is StageOutcome.FAILED
    assert ports.archived()
    assert len(ports.events.sent) == 1


async def test_a_failed_archive_is_reported_and_sends_no_event() -> None:
    class ArchiveRefused(InMemoryIncidentConversation):
        async def archive(self, conversation: ConversationReference) -> OperationResult[None]:
            return OperationResult.permanent_error("Slack archive failed: restricted_action", ErrorCode.CONVERSATION_NOT_WRITABLE)

    ports = await _Ports.seeded(ArchiveRefused(open_ids=[CHANNEL_ID]))

    archive = _done(await ports.archive())

    assert await ports.stored_status() is IncidentStatus.CLOSED
    assert archive.archive.outcome is StageOutcome.FAILED
    assert ports.events.sent == []


async def test_archiving_a_closed_incident_reruns_the_followers_and_archives() -> None:
    ports = await _Ports.seeded()
    await ports.incidents.set_status(INCIDENT_ID, IncidentStatus.CLOSED, at=AT)

    archive = _done(await ports.archive())

    assert archive.change.previous is IncidentStatus.CLOSED
    assert ports.posts() == (STATUS_NOTICE, ARCHIVED_NOTICE)
    assert ports.archived()
    assert len(ports.events.sent) == 1
