"""Unit tests for summarizing an incident conversation: window, limit and transcript gathering in the service."""

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from contracts.operations import OperationResult, OperationStatus
from packages.incident.core.api import IncidentTranscriptReader, TranscriptMessage
from packages.incident.scribe import service
from packages.incident.scribe.service import EMPTY_HISTORY_CODE, summarize_incident_conversation
from packages.incident.scribe.settings import IncidentSummarySettings

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
_STARTED = datetime(2026, 2, 28, 9, 30, tzinfo=UTC)
_MESSAGES = (
    TranscriptMessage(author="Ada", text="prod is down", posted_at=_STARTED),
    TranscriptMessage(author="Bob", text="on it, rolling back"),
)


class FakeTranscriptReader:
    """In-memory ``IncidentTranscriptReader`` that records how it was asked."""

    def __init__(self, messages: Sequence[TranscriptMessage] = _MESSAGES, started_at: datetime | None = _STARTED) -> None:
        self._messages = messages
        self._started_at = started_at
        self.start_lookups: list[str] = []
        self.reads: list[dict[str, Any]] = []

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        self.start_lookups.append(conversation_id)
        return self._started_at

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        self.reads.append(
            {
                "conversation_id": conversation_id,
                "since": since,
                "limit": limit,
                "exclude_own_and_system_messages": exclude_own_and_system_messages,
            }
        )
        return self._messages


@pytest.fixture(autouse=True)
def _fixed_clock_and_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the service clock and the history settings so windows and limits are exact."""
    settings = IncidentSummarySettings.model_validate(
        {
            "INCIDENT_SUMMARY__DEFAULT_HISTORY_LIMIT": 200,
            "INCIDENT_SUMMARY__MAX_HISTORY_LIMIT": 500,
            "INCIDENT_SUMMARY__DEFAULT_SINCE_HOURS": 24,
            "INCIDENT_SUMMARY__TIMEZONE": "America/Toronto",
        }
    )
    monkeypatch.setattr(service, "get_incident_summary_settings", lambda: settings)
    monkeypatch.setattr(service, "_now", lambda: _NOW)


@pytest.fixture
def summarize(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncMock]:
    """Stub ``summarize_transcript`` so the gathering is observed without a model call."""
    stub = AsyncMock(return_value=OperationResult.success(data="the summary"))
    monkeypatch.setattr(service, "summarize_transcript", stub)
    yield stub


def test_fake_reader_satisfies_the_interface() -> None:
    """The fake stands in for the real reader only if it matches the interface."""
    assert isinstance(FakeTranscriptReader(), IncidentTranscriptReader)


class TestWindow:
    async def test_since_reads_from_now_minus_since_without_asking_for_the_start(self, summarize: AsyncMock) -> None:
        """An explicit look-back is measured from now, and the conversation's start is never looked up."""
        reader = FakeTranscriptReader()

        await summarize_incident_conversation("C123", since=timedelta(hours=2), reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=2)
        assert reader.start_lookups == []

    async def test_without_since_the_window_starts_when_the_conversation_started(self, summarize: AsyncMock) -> None:
        """With no look-back the summary covers the whole incident, from the conversation's start."""
        reader = FakeTranscriptReader()

        await summarize_incident_conversation("C123", reader=reader)

        assert reader.start_lookups == ["C123"]
        assert reader.reads[0]["since"] == _STARTED

    async def test_unknown_start_falls_back_to_the_default_window(self, summarize: AsyncMock) -> None:
        """When the reader cannot say when the conversation started, the configured default look-back applies."""
        reader = FakeTranscriptReader(started_at=None)

        await summarize_incident_conversation("C123", reader=reader)

        assert reader.reads[0]["since"] == _NOW - timedelta(hours=24)


class TestLimit:
    @pytest.mark.parametrize(
        ("limit", "expected"),
        [(None, 200), (0, 200), (-5, 200), (50, 50), (500, 500), (9999, 500)],
    )
    async def test_limit_defaults_when_missing_or_not_positive_and_is_capped(
        self, summarize: AsyncMock, limit: int | None, expected: int
    ) -> None:
        """A missing, zero or negative limit means the default; a larger one is capped at the maximum."""
        reader = FakeTranscriptReader()

        await summarize_incident_conversation("C123", limit=limit, reader=reader)

        assert reader.reads[0]["limit"] == expected


class TestGathering:
    async def test_transcript_and_instructions_reach_summarize_transcript(self, summarize: AsyncMock) -> None:
        """The messages the reader returned are passed on positionally and untouched, with the caller's instructions."""
        reader = FakeTranscriptReader()

        result = await summarize_incident_conversation("C123", instructions="use mrkdwn", reader=reader)

        summarize.assert_awaited_once_with(_MESSAGES, instructions="use mrkdwn")
        assert result is summarize.return_value

    async def test_transcript_is_read_once_for_the_conversation_without_own_posts_or_system_events(
        self, summarize: AsyncMock
    ) -> None:
        """The bot's own scaffolding posts and channel system events are excluded, as for draft and status update."""
        reader = FakeTranscriptReader()

        await summarize_incident_conversation("C123", reader=reader)

        assert len(reader.reads) == 1
        assert reader.reads[0]["conversation_id"] == "C123"
        assert reader.reads[0]["exclude_own_and_system_messages"] is True

    async def test_reader_defaults_to_the_core_provider(self, summarize: AsyncMock, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no reader passed, the one the incident core provider resolves is used."""
        reader = FakeTranscriptReader()
        monkeypatch.setattr(service, "get_incident_transcript_reader", lambda: reader)

        await summarize_incident_conversation("C123")

        assert len(reader.reads) == 1

    async def test_model_receives_the_current_time_and_time_stamped_lines_in_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The model sees now and each message's time in the summary timezone; an untimed message has no prefix."""
        summarizer = MagicMock()
        summarizer.summarize = AsyncMock(return_value=OperationResult.success(data="ok"))
        monkeypatch.setattr(service, "get_summarizer", lambda: summarizer)

        await summarize_incident_conversation("C123", reader=FakeTranscriptReader())

        assert summarizer.summarize.await_args.args[0] == (
            "Current time: 2026-03-01 07:00 EST\n"
            "\n"
            "Incident channel transcript:\n"
            "[2026-02-28 04:30 EST] Ada: prod is down\n"
            "Bob: on it, rolling back"
        )


class TestFailures:
    async def test_empty_transcript_gives_the_empty_history_error(self) -> None:
        """Nothing read (no messages, or a platform failure behind the reader) is the empty-history outcome."""
        result = await summarize_incident_conversation("C123", reader=FakeTranscriptReader(messages=()))

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == EMPTY_HISTORY_CODE

    async def test_summarizer_error_is_returned_unchanged(self, summarize: AsyncMock) -> None:
        """The classified error from summarizing is the caller's result, not rewrapped."""
        error: OperationResult[str] = OperationResult.transient_error(message="boom", error_code="SERVER_ERROR")
        summarize.return_value = error

        assert await summarize_incident_conversation("C123", reader=FakeTranscriptReader()) is error
