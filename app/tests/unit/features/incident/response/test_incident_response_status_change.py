"""``change_status``: the record first, then the report status line, the list projection and the channel.

Runs over the core in-memory fakes (incident store, report, list projection and
conversation), which the core parity suites hold to the adapters' rules; a
test-local subclass fails one port or records the call order. Assertions read
the fakes back in domain terms (the stored status, the report's status line, the
list row's status cell, the channel's posts) and the stage outcomes the service
returns, since the entry point renders its reply from those outcomes.

The record is the commit point (decisions/incident-management.md): a refused
command check or a failed record write writes nothing else; a failed follower
write is reported and the rest still run.
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
from features.incident.core.api import ConversationReference, Incident, MessageReference, ReportReference
from features.incident.response.service.status import StageOutcome, StatusChange, change_status
from tests.factories.incident import GOOGLE_TENANT, binding_on, incident_on, slack_conversation

pytestmark = pytest.mark.unit

CHANNEL_ID = "C0INCIDENT"
INCIDENT_ID = "inc-1"
AT = datetime(2026, 11, 16, 15, 0, tzinfo=UTC)
NOTICE = "<@U0INVOKER> has updated the incident status to Closed."


class _Ports:
    """The four ports over in-memory fakes, the incident seeded with its report and open channel (built by ``seeded``)."""

    def __init__(self, reports: InMemoryIncidentReport, report: ReportReference | None) -> None:
        self.reports = reports
        self.incident = replace(incident_on(CHANNEL_ID, INCIDENT_ID), report=report)
        self.incidents = InMemoryIncidentStore()
        self.incidents.seed(self.incident)
        self.projection = InMemoryIncidentListProjection()
        self.conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID])

    @classmethod
    async def seeded(cls, *, with_report: bool = True) -> Self:
        reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0", next_ids=["D0"])
        report: ReportReference | None = None
        if with_report:
            created = await reports.create_from_template("Incident")
            assert created.data is not None
            report = created.data
        return cls(reports, report)

    async def change(self, status: IncidentStatus = IncidentStatus.CLOSED) -> OperationResult[StatusChange]:
        return await change_status(
            self.incidents,
            self.reports,
            self.projection,
            self.conversations,
            slack_conversation(CHANNEL_ID),
            status,
            at=AT,
            notice=NOTICE,
        )

    async def stored_status(self) -> IncidentStatus:
        found = await self.incidents.get(INCIDENT_ID)
        assert found.data is not None
        return found.data.status

    def list_status(self) -> str:
        [row] = self.projection.rows
        return row[3]

    def posts(self) -> tuple[str, ...]:
        return tuple(self.conversations.posts_in(slack_conversation(CHANNEL_ID)))


def _changed(result: OperationResult[StatusChange]) -> StatusChange:
    assert result.is_success and result.data is not None, result
    return result.data


async def test_a_status_change_writes_the_record_the_report_the_list_and_the_channel() -> None:
    ports = await _Ports.seeded()

    change = _changed(await ports.change(IncidentStatus.READY_TO_BE_REVIEWED))

    assert await ports.stored_status() is IncidentStatus.READY_TO_BE_REVIEWED
    assert ports.incident.report is not None
    assert ports.reports.status_text_of(ports.incident.report) is IncidentStatus.READY_TO_BE_REVIEWED
    assert ports.list_status() == "Ready to be Reviewed"
    assert ports.posts() == (NOTICE,)
    assert (change.previous, change.incident.status) == (IncidentStatus.OPEN, IncidentStatus.READY_TO_BE_REVIEWED)
    assert [stage.outcome for stage in (change.report, change.projection, change.channel)] == [StageOutcome.DONE] * 3


async def test_the_writes_run_record_report_list_then_channel() -> None:
    calls: list[str] = []
    ports = await _Ports.seeded()

    class Store(InMemoryIncidentStore):
        async def set_status(self, incident_id: str, status: IncidentStatus, *, at: datetime) -> OperationResult[Incident]:
            calls.append("record")
            return await super().set_status(incident_id, status, at=at)

    class Report(InMemoryIncidentReport):
        async def set_status_text(self, report: ReportReference, status: IncidentStatus) -> OperationResult[None]:
            calls.append("report")
            return await super().set_status_text(report, status)

    class Projection(InMemoryIncidentListProjection):
        async def update_status(self, incident: Incident, status: IncidentStatus) -> OperationResult[None]:
            calls.append("list")
            return await super().update_status(incident, status)

    class Conversation(InMemoryIncidentConversation):
        async def post(self, conversation: ConversationReference, text: str, *, blocks=()) -> OperationResult[MessageReference]:  # type: ignore[no-untyped-def]
            calls.append("channel")
            return await super().post(conversation, text, blocks=blocks)

    store = Store()
    store.seed(ports.incident)
    report = Report(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0", next_ids=["D0"])
    await report.create_from_template("Incident")

    await change_status(
        store,
        report,
        Projection(),
        Conversation(open_ids=[CHANNEL_ID]),
        slack_conversation(CHANNEL_ID),
        IncidentStatus.CLOSED,
        at=AT,
        notice=NOTICE,
    )

    assert calls == ["record", "report", "list", "channel"]


async def test_closing_takes_the_incident_off_the_open_list_and_reopening_puts_it_back() -> None:
    ports = await _Ports.seeded()

    _changed(await ports.change(IncidentStatus.CLOSED))
    closed = await ports.incidents.list_open()
    _changed(await ports.change(IncidentStatus.IN_PROGRESS))
    reopened = await ports.incidents.list_open()

    assert list(closed.data or ()) == []
    assert [incident.id for incident in reopened.data or ()] == [INCIDENT_ID]


async def test_repeating_a_status_rewrites_the_report_the_list_and_the_channel() -> None:
    """A replay writes no record change but reruns the followers, which is how a failed follower is repaired."""
    ports = await _Ports.seeded()
    _changed(await ports.change(IncidentStatus.CLOSED))

    change = _changed(await ports.change(IncidentStatus.CLOSED))

    assert change.previous is IncidentStatus.CLOSED
    assert [stage.outcome for stage in (change.report, change.projection, change.channel)] == [StageOutcome.DONE] * 3
    assert ports.posts() == (NOTICE, NOTICE)


async def test_a_conversation_of_no_incident_is_refused_and_nothing_is_written() -> None:
    ports = await _Ports.seeded()

    result = await change_status(
        ports.incidents,
        ports.reports,
        ports.projection,
        ports.conversations,
        slack_conversation("C0OTHER"),
        IncidentStatus.CLOSED,
        at=AT,
        notice=NOTICE,
    )

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT
    assert await ports.stored_status() is IncidentStatus.OPEN
    assert (ports.projection.rows, ports.posts()) == ([], ())


async def test_a_failed_record_write_stops_before_the_report_the_list_and_the_channel() -> None:
    ports = await _Ports.seeded()

    class Store(InMemoryIncidentStore):
        async def set_status(self, incident_id: str, status: IncidentStatus, *, at: datetime) -> OperationResult[Incident]:
            return OperationResult.permanent_error("conflict", ErrorCode.INCIDENT_RECORD_CONFLICT)

    store = Store()
    store.seed(ports.incident)

    result = await change_status(
        store,
        ports.reports,
        ports.projection,
        ports.conversations,
        slack_conversation(CHANNEL_ID),
        IncidentStatus.CLOSED,
        at=AT,
        notice=NOTICE,
    )

    assert result.error_code == ErrorCode.INCIDENT_RECORD_CONFLICT
    assert ports.incident.report is not None
    assert ports.reports.status_text_of(ports.incident.report) is None
    assert (ports.projection.rows, ports.posts()) == ([], ())


async def test_a_failed_report_write_is_reported_and_the_list_and_channel_still_move() -> None:
    ports = await _Ports.seeded()
    ports.reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")

    change = _changed(await ports.change())

    assert (change.report.outcome, change.report.error_code) == (StageOutcome.FAILED, None)
    assert change.report.status is OperationStatus.NOT_FOUND
    assert ports.list_status() == "Closed"
    assert ports.posts() == (NOTICE,)


async def test_a_failed_list_write_is_reported_and_the_channel_still_moves() -> None:
    ports = await _Ports.seeded()
    ports.projection = InMemoryIncidentListProjection(
        fail_with=OperationResult.permanent_error("no sheet", ErrorCode.CONFIG_NOT_CONFIGURED)
    )

    change = _changed(await ports.change())

    assert (change.projection.outcome, change.projection.error_code) == (StageOutcome.FAILED, ErrorCode.CONFIG_NOT_CONFIGURED)
    assert change.report.outcome is StageOutcome.DONE
    assert ports.posts() == (NOTICE,)


async def test_a_failed_post_is_reported_after_every_other_write() -> None:
    ports = await _Ports.seeded()

    class Conversation(InMemoryIncidentConversation):
        async def post(self, conversation: ConversationReference, text: str, *, blocks=()) -> OperationResult[MessageReference]:  # type: ignore[no-untyped-def]
            return OperationResult.transient_error("slack down")

    ports.conversations = Conversation(open_ids=[CHANNEL_ID])

    change = _changed(await ports.change())

    assert change.channel.outcome is StageOutcome.FAILED
    assert ports.list_status() == "Closed"
    assert await ports.stored_status() is IncidentStatus.CLOSED


async def test_every_follower_failing_still_keeps_the_record_change() -> None:
    ports = await _Ports.seeded()
    ports.reports = InMemoryIncidentReport(tenant=GOOGLE_TENANT, folder_id="F0", report_template_id="T0")
    ports.projection = InMemoryIncidentListProjection(fail_with=OperationResult.transient_error("sheets down"))
    ports.conversations = InMemoryIncidentConversation()

    change = _changed(await ports.change())

    assert [stage.outcome for stage in (change.report, change.projection, change.channel)] == [StageOutcome.FAILED] * 3
    assert await ports.stored_status() is IncidentStatus.CLOSED


async def test_an_incident_without_a_report_skips_the_report_line() -> None:
    ports = await _Ports.seeded(with_report=False)

    change = _changed(await ports.change())

    assert (change.report.outcome, change.report.reason) == (StageOutcome.SKIPPED, "no_report")
    assert ports.list_status() == "Closed"
    assert ports.posts() == (NOTICE,)


async def test_an_archived_channel_skips_the_post_and_keeps_every_other_write() -> None:
    ports = await _Ports.seeded()
    ports.conversations = InMemoryIncidentConversation(archived_ids=[CHANNEL_ID])

    change = _changed(await ports.change())

    assert (change.channel.outcome, change.channel.reason) == (StageOutcome.SKIPPED, "not_writable")
    assert ports.conversations.posts_in(slack_conversation(CHANNEL_ID)) == ()
    assert await ports.stored_status() is IncidentStatus.CLOSED


async def test_a_writability_check_that_fails_is_reported_and_nothing_is_posted() -> None:
    ports = await _Ports.seeded()
    ports.conversations = InMemoryIncidentConversation(non_member_ids=["C0SOMEWHERE"])

    change = _changed(await ports.change())

    assert change.channel.outcome is StageOutcome.FAILED
    assert change.channel.status is OperationStatus.NOT_FOUND


async def test_the_notice_goes_to_the_records_conversation() -> None:
    """The record's primary conversation is told, whichever bound conversation the command came from."""
    ports = await _Ports.seeded()
    ports.incidents.bind(binding_on("C0SIDE", INCIDENT_ID, primary=False))
    ports.conversations = InMemoryIncidentConversation(open_ids=[CHANNEL_ID, "C0SIDE"])

    _changed(
        await change_status(
            ports.incidents,
            ports.reports,
            ports.projection,
            ports.conversations,
            slack_conversation("C0SIDE"),
            IncidentStatus.CLOSED,
            at=AT,
            notice=NOTICE,
        )
    )

    assert ports.posts() == (NOTICE,)
    assert ports.conversations.posts_in(slack_conversation("C0SIDE")) == ()
