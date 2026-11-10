"""Unit tests for drafting from an incident conversation: report lookup, start signal, window, limit and transcript gathering.

The conversation is resolved to its incident through an in-memory incident store
seeded with one incident on Slack channel C123; the report drafted from is the
one the record holds, and the conversation read is the record's reference (its
stored link tells it from the command's). The store, the transcript reader and
the start signal record what they were asked in one shared event list, so order
is observable. A reader failure is a classified ``OperationResult`` the fake
returns on request; the draft gives the same outcome as an empty transcript.
"""

from collections.abc import Iterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.in_memory import InMemoryIncidentReport, InMemoryIncidentStore
from features.incident.core.api import (
    ConversationReference,
    DocumentSection,
    IncidentTranscriptReader,
    ReportReference,
    TranscriptMessage,
)
from features.incident.scribe import service
from features.incident.scribe.domain import DraftedDocument
from features.incident.scribe.service import (
    EMPTY_HISTORY_CODE,
    NO_DOCUMENT_CODE,
    draft_incident_document_from_conversation,
)
from features.incident.scribe.settings import IncidentDraftSettings
from tests.factories.incident import incident_on, slack_conversation

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
_STARTED = datetime(2026, 2, 28, 9, 30, tzinfo=UTC)
_MESSAGES = (
    TranscriptMessage(author="Ada", text="prod is down", posted_at=_STARTED),
    TranscriptMessage(author="Bob", text="on it, rolling back"),
)
_REPORT = ReportReference(
    system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="DOC123", url="https://docs.google.com/document/d/DOC123/edit"
)
_CONVERSATION = slack_conversation("C123")
_RECORDED_CONVERSATION = replace(_CONVERSATION, url="https://example.slack.com/archives/C123")


class FakeTranscriptReader:
    """In-memory ``IncidentTranscriptReader`` that records how it was asked, in a shared event list.

    ``read_fails`` and ``start_fails`` make the read or the start lookup return a
    classified transient failure.
    """

    def __init__(
        self,
        events: list[str],
        messages: Sequence[TranscriptMessage] = _MESSAGES,
        started_at: datetime | None = _STARTED,
        *,
        read_fails: bool = False,
        start_fails: bool = False,
    ) -> None:
        self._events = events
        self._messages = messages
        self._started_at = started_at
        self._read_fails = read_fails
        self._start_fails = start_fails
        self.reads: list[dict[str, Any]] = []

    def conversation_started_at(self, conversation: ConversationReference) -> OperationResult[datetime | None]:
        self._events.append("conversation_started_at")
        if self._start_fails:
            return OperationResult.transient_error("Slack transcript read failed: ratelimited", "ratelimited")
        return OperationResult.success(self._started_at)

    def read_transcript(
        self,
        conversation: ConversationReference,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> OperationResult[Sequence[TranscriptMessage]]:
        self._events.append("read_transcript")
        self.reads.append(
            {
                "conversation": conversation,
                "since": since,
                "limit": limit,
                "exclude_own_and_system_messages": exclude_own_and_system_messages,
            }
        )
        if self._read_fails:
            return OperationResult.transient_error("Slack transcript read failed: ratelimited", "ratelimited")
        return OperationResult.success(self._messages)


class RecordingIncidentStore(InMemoryIncidentStore):
    """In-memory incident store recording each conversation lookup in a shared event list."""

    def __init__(self, events: list[str], *, report: ReportReference | None = _REPORT, seeded: bool = True) -> None:
        super().__init__()
        self._events = events
        self.lookups: list[ConversationReference] = []
        if seeded:
            self.seed(replace(incident_on("C123", "inc-1"), report=report, conversation=_RECORDED_CONVERSATION))

    async def find_by_conversation(self, conversation: ConversationReference) -> OperationResult:
        self._events.append("find_incident")
        self.lookups.append(conversation)
        return await super().find_by_conversation(conversation)


@pytest.fixture(autouse=True)
def _fixed_clock_and_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the service clock and the history settings so windows and limits are exact."""
    settings = IncidentDraftSettings.model_validate(
        {
            "INCIDENT_DRAFT__DEFAULT_HISTORY_LIMIT": 100,
            "INCIDENT_DRAFT__MAX_HISTORY_LIMIT": 200,
            "INCIDENT_DRAFT__DEFAULT_SINCE_HOURS": 24,
        }
    )
    monkeypatch.setattr(service, "get_incident_draft_settings", lambda: settings)
    monkeypatch.setattr(service, "_now", lambda: _NOW)


@pytest.fixture
def events() -> list[str]:
    """Shared, ordered record of what the fakes and the start signal were asked."""
    return []


@pytest.fixture
def draft(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    """Stub ``draft_incident_document`` so the gathering is observed without a document or model call."""
    outcome = DraftedDocument(document_id="NEW1", created=True, drafted_headings=("Trigger",), unanswered_headings=())
    stub = AsyncMock(return_value=OperationResult.success(data=outcome))
    monkeypatch.setattr(service, "draft_incident_document", stub)
    yield stub


def test_fakes_satisfy_the_interfaces() -> None:
    """The fakes stand in for the real implementations only if they match the interfaces."""
    assert isinstance(FakeTranscriptReader([]), IncidentTranscriptReader)


class TestReportDocument:
    async def test_the_records_report_and_transcript_reach_draft_incident_document(
        self, draft: AsyncMock, events: list[str]
    ) -> None:
        """The incident's report reference and the messages read are passed on positionally and untouched."""
        store = RecordingIncidentStore(events)

        result = await draft_incident_document_from_conversation(store, _CONVERSATION, reader=FakeTranscriptReader(events))

        assert store.lookups == [_CONVERSATION]
        draft.assert_awaited_once_with(_REPORT, _MESSAGES)
        assert result is draft.return_value

    @pytest.mark.parametrize(
        "store_args",
        [pytest.param({"report": None}, id="record-without-report"), pytest.param({"seeded": False}, id="not-an-incident")],
    )
    async def test_no_report_gives_the_no_document_error(
        self, draft: AsyncMock, events: list[str], store_args: dict[str, Any]
    ) -> None:
        """A channel that is no incident, or an incident without a report, ends the run before anything slow."""
        started: list[int] = []
        reader = FakeTranscriptReader(events)

        result = await draft_incident_document_from_conversation(
            RecordingIncidentStore(events, **store_args), _CONVERSATION, on_started=lambda: started.append(1), reader=reader
        )

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == NO_DOCUMENT_CODE
        assert started == []
        assert events == ["find_incident"]
        draft.assert_not_awaited()

    async def test_another_incident_lookup_failure_is_returned_unchanged(self, draft: AsyncMock, events: list[str]) -> None:
        """A store failure other than not-an-incident keeps its classification; nothing is read or drafted."""
        failure: OperationResult[Any] = OperationResult.transient_error(message="store down", error_code="STORE")
        store = MagicMock()
        store.find_by_conversation = AsyncMock(return_value=failure)

        result = await draft_incident_document_from_conversation(store, _CONVERSATION, reader=FakeTranscriptReader(events))

        assert result.status is OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "STORE"
        assert events == []
        draft.assert_not_awaited()


class TestStartSignal:
    async def test_on_started_is_called_once_after_the_lookup_and_before_the_transcript_is_read(
        self, draft: AsyncMock, events: list[str]
    ) -> None:
        """The signal marks the start of the slow work: the report is known, nothing has been read yet."""
        await draft_incident_document_from_conversation(
            RecordingIncidentStore(events),
            _CONVERSATION,
            on_started=lambda: events.append("on_started"),
            reader=FakeTranscriptReader(events),
        )

        assert events == ["find_incident", "on_started", "conversation_started_at", "read_transcript"]

    async def test_on_started_may_be_omitted(self, draft: AsyncMock, events: list[str]) -> None:
        """A caller with nothing to signal still gets its draft."""
        result = await draft_incident_document_from_conversation(
            RecordingIncidentStore(events), _CONVERSATION, reader=FakeTranscriptReader(events)
        )

        assert result.is_success


class TestWindowAndLimit:
    async def test_the_window_starts_when_the_conversation_started(self, draft: AsyncMock, events: list[str]) -> None:
        """A draft covers the whole incident, from the conversation's start."""
        reader = FakeTranscriptReader(events)

        await draft_incident_document_from_conversation(RecordingIncidentStore(events), _CONVERSATION, reader=reader)

        assert reader.reads[0]["since"] == _STARTED

    async def test_unknown_start_falls_back_to_the_default_window(self, draft: AsyncMock, events: list[str]) -> None:
        """When the reader cannot say when the conversation started, the configured default look-back applies."""
        reader = FakeTranscriptReader(events, started_at=None)

        await draft_incident_document_from_conversation(RecordingIncidentStore(events), _CONVERSATION, reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=24)

    @pytest.mark.parametrize(
        ("limit", "expected"),
        [(None, 100), (0, 100), (-5, 100), (50, 50), (200, 200), (999, 200)],
    )
    async def test_limit_defaults_when_missing_or_not_positive_and_is_capped(
        self, draft: AsyncMock, events: list[str], limit: int | None, expected: int
    ) -> None:
        """A missing, zero or negative limit means the default; a larger one is capped at the maximum."""
        reader = FakeTranscriptReader(events)

        await draft_incident_document_from_conversation(RecordingIncidentStore(events), _CONVERSATION, limit=limit, reader=reader)

        assert reader.reads[0]["limit"] == expected

    async def test_a_failed_start_lookup_falls_back_to_the_default_window(self, draft: AsyncMock, events: list[str]) -> None:
        """A classified failure of the start lookup is treated like an unknown start."""
        reader = FakeTranscriptReader(events, start_fails=True)

        await draft_incident_document_from_conversation(RecordingIncidentStore(events), _CONVERSATION, reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=24)

    async def test_transcript_is_read_once_for_the_conversation_with_filtering_on(
        self, draft: AsyncMock, events: list[str]
    ) -> None:
        """Drafts leave out the bot's own posts and system events: the read asks for them to be excluded."""
        reader = FakeTranscriptReader(events)

        await draft_incident_document_from_conversation(RecordingIncidentStore(events), _CONVERSATION, reader=reader)

        assert len(reader.reads) == 1
        assert reader.reads[0]["conversation"] == _RECORDED_CONVERSATION
        assert reader.reads[0]["exclude_own_and_system_messages"] is True

    async def test_reader_defaults_to_the_core_provider(
        self, draft: AsyncMock, events: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no reader passed, the one the incident core provider resolves is used."""
        reader = FakeTranscriptReader(events)
        monkeypatch.setattr(service, "get_incident_transcript_reader", lambda: reader)

        await draft_incident_document_from_conversation(RecordingIncidentStore(events), _CONVERSATION)

        assert len(reader.reads) == 1


def _readable_report() -> InMemoryIncidentReport:
    """A report interface holding one draftable section for the record's report, for runs that end before the model call."""
    reports = InMemoryIncidentReport()
    reports.seed_sections(_REPORT, [DocumentSection(heading="Trigger", instructions="What set it off?")])
    return reports


class TestFailures:
    async def test_empty_transcript_gives_the_empty_history_error(
        self, events: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing read is the empty-history outcome."""
        monkeypatch.setattr(service, "get_incident_report", _readable_report)

        result = await draft_incident_document_from_conversation(
            RecordingIncidentStore(events), _CONVERSATION, reader=FakeTranscriptReader(events, messages=())
        )

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == EMPTY_HISTORY_CODE

    async def test_a_failed_read_gives_the_empty_history_error(self, events: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
        """A classified read failure keeps today's reply: the same empty-history outcome as no messages."""
        monkeypatch.setattr(service, "get_incident_report", _readable_report)

        result = await draft_incident_document_from_conversation(
            RecordingIncidentStore(events), _CONVERSATION, reader=FakeTranscriptReader(events, read_fails=True)
        )

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == EMPTY_HISTORY_CODE

    async def test_drafting_error_is_returned_unchanged(self, draft: AsyncMock, events: list[str]) -> None:
        """The classified error from drafting is the caller's result, not rewrapped."""
        error: OperationResult[DraftedDocument] = OperationResult.transient_error(message="boom", error_code="SERVER_ERROR")
        draft.return_value = error

        result = await draft_incident_document_from_conversation(
            RecordingIncidentStore(events), _CONVERSATION, reader=FakeTranscriptReader(events)
        )

        assert result is error
