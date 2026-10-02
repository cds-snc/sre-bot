"""Unit tests for drafting from an incident conversation: report lookup, start signal, window, limit and transcript gathering."""

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from contracts.operations import OperationResult, OperationStatus
from packages.incident.core.api import IncidentTranscriptReader, TranscriptMessage
from packages.incident_draft import providers, service
from packages.incident_draft.domain import DocumentSection, DraftedDocument
from packages.incident_draft.service import (
    EMPTY_HISTORY_CODE,
    NO_DOCUMENT_CODE,
    IncidentReportLinkLookup,
    draft_incident_document_from_conversation,
)
from packages.incident_draft.settings import IncidentDraftSettings

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
_STARTED = datetime(2026, 2, 28, 9, 30, tzinfo=UTC)
_MESSAGES = (
    TranscriptMessage(author="Ada", text="prod is down", posted_at=_STARTED),
    TranscriptMessage(author="Bob", text="on it, rolling back"),
)
_REPORT_LINK = "https://docs.google.com/document/d/DOC123/edit"


class FakeTranscriptReader:
    """In-memory ``IncidentTranscriptReader`` that records how it was asked, in a shared event list."""

    def __init__(
        self,
        events: list[str],
        messages: Sequence[TranscriptMessage] = _MESSAGES,
        started_at: datetime | None = _STARTED,
    ) -> None:
        self._events = events
        self._messages = messages
        self._started_at = started_at
        self.reads: list[dict[str, Any]] = []

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        self._events.append("conversation_started_at")
        return self._started_at

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        self._events.append("read_transcript")
        self.reads.append(
            {
                "conversation_id": conversation_id,
                "since": since,
                "limit": limit,
                "exclude_own_and_system_messages": exclude_own_and_system_messages,
            }
        )
        return self._messages


class FakeReportLinkLookup:
    """In-memory ``IncidentReportLinkLookup`` answering with fixed links, recording in a shared event list."""

    def __init__(self, events: list[str], links: Sequence[str] = (_REPORT_LINK,)) -> None:
        self._events = events
        self._links = links
        self.lookups: list[str] = []

    def find_report_links(self, conversation_id: str) -> Sequence[str]:
        self._events.append("find_report_links")
        self.lookups.append(conversation_id)
        return self._links


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
    assert isinstance(FakeReportLinkLookup([]), IncidentReportLinkLookup)


class TestReportDocument:
    async def test_document_id_and_transcript_reach_draft_incident_document(self, draft: AsyncMock, events: list[str]) -> None:
        """The report's document id and the messages read are passed on positionally and untouched."""
        lookup = FakeReportLinkLookup(events)

        result = await draft_incident_document_from_conversation("C123", reader=FakeTranscriptReader(events), report_links=lookup)

        assert lookup.lookups == ["C123"]
        draft.assert_awaited_once_with("DOC123", _MESSAGES)
        assert result is draft.return_value

    @pytest.mark.parametrize("links", [(), ("https://example.com/not-a-doc",), ("",)])
    async def test_no_usable_report_link_gives_the_no_document_error(
        self, draft: AsyncMock, events: list[str], links: Sequence[str]
    ) -> None:
        """No link, or only links without a document id, ends the run before anything slow: no start signal, no read."""
        started: list[int] = []
        reader = FakeTranscriptReader(events)

        result = await draft_incident_document_from_conversation(
            "C123", on_started=lambda: started.append(1), reader=reader, report_links=FakeReportLinkLookup(events, links)
        )

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == NO_DOCUMENT_CODE
        assert started == []
        assert events == ["find_report_links"]
        draft.assert_not_awaited()

    async def test_a_link_without_a_document_id_is_logged(
        self, draft: AsyncMock, events: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A report link that is not a Google Docs URL is reported, so a broken bookmark can be found.

        The service's logger is replaced by a mock, so the assertion does not
        depend on the process-wide structlog configuration.
        """
        logger = MagicMock()
        monkeypatch.setattr(service, "logger", logger)
        lookup = FakeReportLinkLookup(events, ("https://example.com/not-a-doc",))

        await draft_incident_document_from_conversation("C123", reader=FakeTranscriptReader(events), report_links=lookup)

        logger.bind.return_value.warning.assert_called_once_with(
            "incident_draft_bookmark_link_invalid", link="https://example.com/not-a-doc"
        )

    async def test_an_invalid_link_is_skipped_for_the_next_valid_one(self, draft: AsyncMock, events: list[str]) -> None:
        """The first link carrying a document id wins, whatever precedes it."""
        lookup = FakeReportLinkLookup(
            events,
            (
                "https://example.com/not-a-doc",
                "https://docs.google.com/document/d/DOC-second/edit",
                "https://docs.google.com/document/d/DOC-third/edit",
            ),
        )

        await draft_incident_document_from_conversation("C123", reader=FakeTranscriptReader(events), report_links=lookup)

        assert draft.await_args.args[0] == "DOC-second"

    async def test_lookup_defaults_to_the_package_provider(
        self, draft: AsyncMock, events: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no lookup passed, the one the package provider resolves is used."""
        lookup = FakeReportLinkLookup(events)
        monkeypatch.setattr(providers, "get_incident_report_link_lookup", lambda: lookup)

        await draft_incident_document_from_conversation("C123", reader=FakeTranscriptReader(events))

        assert lookup.lookups == ["C123"]


class TestStartSignal:
    async def test_on_started_is_called_once_after_the_lookup_and_before_the_transcript_is_read(
        self, draft: AsyncMock, events: list[str]
    ) -> None:
        """The signal marks the start of the slow work: the report is known, nothing has been read yet."""
        await draft_incident_document_from_conversation(
            "C123",
            on_started=lambda: events.append("on_started"),
            reader=FakeTranscriptReader(events),
            report_links=FakeReportLinkLookup(events),
        )

        assert events == ["find_report_links", "on_started", "conversation_started_at", "read_transcript"]

    async def test_on_started_may_be_omitted(self, draft: AsyncMock, events: list[str]) -> None:
        """A caller with nothing to signal still gets its draft."""
        result = await draft_incident_document_from_conversation(
            "C123", reader=FakeTranscriptReader(events), report_links=FakeReportLinkLookup(events)
        )

        assert result.is_success


class TestWindowAndLimit:
    async def test_the_window_starts_when_the_conversation_started(self, draft: AsyncMock, events: list[str]) -> None:
        """A draft covers the whole incident, from the conversation's start."""
        reader = FakeTranscriptReader(events)

        await draft_incident_document_from_conversation("C123", reader=reader, report_links=FakeReportLinkLookup(events))

        assert reader.reads[0]["since"] == _STARTED

    async def test_unknown_start_falls_back_to_the_default_window(self, draft: AsyncMock, events: list[str]) -> None:
        """When the reader cannot say when the conversation started, the configured default look-back applies."""
        reader = FakeTranscriptReader(events, started_at=None)

        await draft_incident_document_from_conversation("C123", reader=reader, report_links=FakeReportLinkLookup(events))

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

        await draft_incident_document_from_conversation(
            "C123", limit=limit, reader=reader, report_links=FakeReportLinkLookup(events)
        )

        assert reader.reads[0]["limit"] == expected

    async def test_transcript_is_read_once_for_the_conversation_with_filtering_on(
        self, draft: AsyncMock, events: list[str]
    ) -> None:
        """Drafts leave out the bot's own posts and system events: the read asks for them to be excluded."""
        reader = FakeTranscriptReader(events)

        await draft_incident_document_from_conversation("C123", reader=reader, report_links=FakeReportLinkLookup(events))

        assert len(reader.reads) == 1
        assert reader.reads[0]["conversation_id"] == "C123"
        assert reader.reads[0]["exclude_own_and_system_messages"] is True

    async def test_reader_defaults_to_the_core_provider(
        self, draft: AsyncMock, events: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no reader passed, the one the incident core provider resolves is used."""
        reader = FakeTranscriptReader(events)
        monkeypatch.setattr(service, "get_incident_transcript_reader", lambda: reader)

        await draft_incident_document_from_conversation("C123", report_links=FakeReportLinkLookup(events))

        assert len(reader.reads) == 1


class _ReadableDocument:
    """Document store with one draftable section and no write path, for runs that end before the model call."""

    def read_sections(self, document_id: str) -> list[DocumentSection]:
        return [DocumentSection(heading="Trigger", instructions="What set it off?")]


class TestFailures:
    async def test_empty_transcript_gives_the_empty_history_error(
        self, events: list[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing read (no messages, or a platform failure behind the reader) is the empty-history outcome."""
        monkeypatch.setattr(providers, "get_incident_document_store", _ReadableDocument)

        result = await draft_incident_document_from_conversation(
            "C123", reader=FakeTranscriptReader(events, messages=()), report_links=FakeReportLinkLookup(events)
        )

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == EMPTY_HISTORY_CODE

    async def test_drafting_error_is_returned_unchanged(self, draft: AsyncMock, events: list[str]) -> None:
        """The classified error from drafting is the caller's result, not rewrapped."""
        error: OperationResult[DraftedDocument] = OperationResult.transient_error(message="boom", error_code="SERVER_ERROR")
        draft.return_value = error

        result = await draft_incident_document_from_conversation(
            "C123", reader=FakeTranscriptReader(events), report_links=FakeReportLinkLookup(events)
        )

        assert result is error
