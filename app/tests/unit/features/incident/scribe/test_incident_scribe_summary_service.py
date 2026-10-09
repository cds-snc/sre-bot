"""Tests for the platform-agnostic incident scribe service: summarizing a transcript."""

from datetime import UTC, datetime

import pytest

from contracts.operations import OperationResult, OperationStatus
from features.incident.core.api import TranscriptMessage
from features.incident.scribe import service
from features.incident.scribe.service import EMPTY_HISTORY_CODE, summarize_transcript
from features.incident.scribe.settings import IncidentSummarySettings

pytestmark = pytest.mark.unit

# 2026-09-25 16:00 UTC is 12:00 EDT in Toronto.
_NOW = datetime(2026, 9, 25, 16, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fixed_clock_and_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the service clock and the summary timezone so rendered times are exact."""
    settings = IncidentSummarySettings.model_validate({"INCIDENT_SUMMARY__TIMEZONE": "America/Toronto"})
    monkeypatch.setattr(service, "get_incident_summary_settings", lambda: settings)
    monkeypatch.setattr(service, "_now", lambda: _NOW)


class _StubSummarizer:
    """Minimal ``Summarizer`` stub capturing the transcript it receives."""

    def __init__(self, result: OperationResult[str]) -> None:
        self._result = result
        self.received_transcript: str | None = None
        self.received_instructions: str | None = None
        self.calls = 0

    async def summarize(self, transcript: str, *, instructions: str | None = None) -> OperationResult[str]:
        self.calls += 1
        self.received_transcript = transcript
        self.received_instructions = instructions
        return self._result


class TestSummarizeTranscript:
    @pytest.mark.asyncio
    async def test_empty_history_returns_permanent_error_without_calling_summarizer(self):
        stub = _StubSummarizer(OperationResult.success(data="unused"))

        result = await summarize_transcript([], summarizer=stub)

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == EMPTY_HISTORY_CODE
        assert stub.calls == 0

    @pytest.mark.asyncio
    async def test_success_builds_chronological_transcript_and_returns_summary(self):
        stub = _StubSummarizer(OperationResult.success(data="A tidy summary"))
        messages = [
            TranscriptMessage(author="Ada", text="prod is down"),
            TranscriptMessage(author="Bob", text="on it, rolling back"),
        ]

        result = await summarize_transcript(messages, summarizer=stub)

        assert result.is_success
        assert result.data == "A tidy summary"
        assert stub.received_transcript is not None
        assert stub.received_transcript.endswith("Ada: prod is down\nBob: on it, rolling back")

    @pytest.mark.asyncio
    async def test_lines_carry_their_local_time_and_the_request_states_the_current_time(self):
        """The model sees when each message was posted and what time it is now, both in the summary timezone.

        Without times a multi-day transcript reads as one moment, so an early
        measure that was later lifted looks current. A message without a time
        is rendered without a prefix rather than dropped.
        """
        stub = _StubSummarizer(OperationResult.success(data="ok"))
        messages = [
            TranscriptMessage(author="Ada", text="prod is down", posted_at=datetime(2026, 9, 17, 3, 56, tzinfo=UTC)),
            TranscriptMessage(author="Bob", text="on it"),
        ]

        await summarize_transcript(messages, summarizer=stub)

        assert stub.received_transcript == (
            "Current time: 2026-09-25 12:00 EDT\n"
            "\n"
            "Incident channel transcript:\n"
            "[2026-09-16 23:56 EDT] Ada: prod is down\n"
            "Bob: on it"
        )

    @pytest.mark.asyncio
    async def test_multi_day_transcript_keeps_a_later_reversal_after_the_earlier_state(self):
        """A measure reported working on day one and lifted a week later reaches the model in that order, each dated.

        The order and the dates are what let the model tell the lifted geo-block
        from the current state; the instructions tell it to use them.
        """
        stub = _StubSummarizer(OperationResult.success(data="ok"))
        messages = [
            TranscriptMessage(
                author="Nathaniel",
                text="All out-of-country requests are blocked now.",
                posted_at=datetime(2026, 9, 17, 14, 52, tzinfo=UTC),
            ),
            TranscriptMessage(
                author="Nathaniel",
                text="Either that or we block PK at the WAF again.",
                posted_at=datetime(2026, 9, 24, 13, 13, tzinfo=UTC),
            ),
        ]

        await summarize_transcript(messages, summarizer=stub)

        assert stub.received_transcript is not None
        transcript_lines = stub.received_transcript.splitlines()[-2:]
        assert transcript_lines == [
            "[2026-09-17 10:52 EDT] Nathaniel: All out-of-country requests are blocked now.",
            "[2026-09-24 09:13 EDT] Nathaniel: Either that or we block PK at the WAF again.",
        ]

    @pytest.mark.asyncio
    async def test_instructions_tell_the_model_to_judge_current_status_by_recency(self):
        """The content prompt carries the recency rules that keep superseded facts out of the current status."""
        stub = _StubSummarizer(OperationResult.success(data="ok"))

        await summarize_transcript([TranscriptMessage(author="Ada", text="prod is down")], summarizer=stub)

        instructions = stub.received_instructions or ""
        assert "Later messages supersede earlier ones" in instructions
        assert "current time" in instructions
        assert "last confirmed" in instructions
        assert "past tense" in instructions
        assert "no later message answers" in instructions

    @pytest.mark.asyncio
    async def test_content_prompt_is_always_sent_and_formatting_is_appended(self):
        stub = _StubSummarizer(OperationResult.success(data="ok"))
        messages = [TranscriptMessage(author="Ada", text="prod is down")]

        await summarize_transcript(messages, instructions="USE SLACK MRKDWN", summarizer=stub)

        assert stub.received_instructions is not None
        # Feature content prompt is always present...
        assert "incident-response assistant" in stub.received_instructions
        # ...with the caller's platform formatting appended after it.
        assert stub.received_instructions.endswith("USE SLACK MRKDWN")

    @pytest.mark.asyncio
    async def test_content_prompt_sent_without_extra_instructions(self):
        stub = _StubSummarizer(OperationResult.success(data="ok"))
        messages = [TranscriptMessage(author="Ada", text="prod is down")]

        await summarize_transcript(messages, summarizer=stub)

        assert stub.received_instructions is not None
        assert "incident-response assistant" in stub.received_instructions

    @pytest.mark.asyncio
    async def test_summarizer_error_is_propagated(self):
        error = OperationResult.transient_error(message="rate limited", error_code="RATE_LIMITED", retry_after=7)
        stub = _StubSummarizer(error)
        messages = [TranscriptMessage(author="Ada", text="hello")]

        result = await summarize_transcript(messages, summarizer=stub)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 7
