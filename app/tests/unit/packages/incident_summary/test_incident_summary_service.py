"""Tests for the platform-agnostic incident_summary service."""

from __future__ import annotations

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.incident_summary.service import (
    EMPTY_HISTORY_CODE,
    TranscriptMessage,
    summarize_transcript,
)

pytestmark = pytest.mark.unit


class _StubSummarizer:
    """Minimal ``Summarizer`` stub capturing the transcript it receives."""

    def __init__(self, result: OperationResult[str]) -> None:
        self._result = result
        self.received_transcript: str | None = None
        self.received_instructions: str | None = None
        self.calls = 0

    async def summarize(
        self, transcript: str, *, instructions: str | None = None
    ) -> OperationResult[str]:
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
        assert stub.received_transcript == "Ada: prod is down\nBob: on it, rolling back"

    @pytest.mark.asyncio
    async def test_content_prompt_is_always_sent_and_formatting_is_appended(self):
        stub = _StubSummarizer(OperationResult.success(data="ok"))
        messages = [TranscriptMessage(author="Ada", text="prod is down")]

        await summarize_transcript(
            messages, instructions="USE SLACK MRKDWN", summarizer=stub
        )

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
        error = OperationResult.transient_error(
            message="rate limited", error_code="RATE_LIMITED", retry_after=7
        )
        stub = _StubSummarizer(error)
        messages = [TranscriptMessage(author="Ada", text="hello")]

        result = await summarize_transcript(messages, summarizer=stub)

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "RATE_LIMITED"
        assert result.retry_after == 7
