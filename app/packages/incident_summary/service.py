"""Platform-agnostic incident-summary business logic.

Builds a chat transcript from platform-neutral messages and delegates to the
``Summarizer`` port (``integrations.openai``) to produce a catch-up summary
for a responder joining an incident channel.

This module is deliberately free of Slack and HTTP imports: it consumes
``TranscriptMessage`` values and returns an ``OperationResult`` so any
platform adapter can reuse it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import structlog

from infrastructure.operations import OperationResult
from integrations.openai import Summarizer, get_summarizer

logger = structlog.get_logger()

EMPTY_HISTORY_CODE = "EMPTY_HISTORY"

# Incident-response content prompt owned by this feature. Platform adapters
# supply additional formatting instructions (e.g. Slack mrkdwn) that are
# appended to this base prompt.
_CONTENT_INSTRUCTIONS = (
    "You are an incident-response assistant. Summarize the following chat "
    "transcript from an incident channel so that a responder joining now can "
    "quickly catch up. Be brief and high-signal -- aim for a summary readable "
    "in under 30 seconds. Cover, each in at most 1-2 short sentences: what is "
    "happening, current status, and key actions taken. End with next steps as "
    "short bullets. Prefer fewer, denser bullets over long chronological logs. "
    "Do not invent details that are not in the transcript."
)


@dataclass(frozen=True)
class TranscriptMessage:
    """A single platform-neutral chat message to be summarized."""

    author: str
    text: str


async def summarize_transcript(
    messages: Sequence[TranscriptMessage],
    *,
    instructions: str | None = None,
    summarizer: Summarizer | None = None,
) -> OperationResult[str]:
    """Summarize a chronological sequence of channel messages.

    Args:
        messages: Chronologically ordered messages to summarize.
        instructions: Optional additional instructions (e.g. platform-specific
            formatting rules) appended to this feature's incident-content
            prompt before being sent to the ``Summarizer`` port.
        summarizer: Optional ``Summarizer`` port; defaults to the process
            singleton. Injected in tests.

    Returns:
        ``OperationResult`` carrying the summary text on success, a permanent
        error with ``EMPTY_HISTORY`` when there is nothing to summarize, or the
        summarizer's classified error otherwise.
    """
    log = logger.bind(operation="summarize_transcript", message_count=len(messages))

    if not messages:
        log.info("incident_summary_empty_history")
        return OperationResult.permanent_error(
            message="No channel history to summarize",
            error_code=EMPTY_HISTORY_CODE,
        )

    transcript = _build_transcript(messages)
    summarizer = summarizer or get_summarizer()
    full_instructions = _CONTENT_INSTRUCTIONS
    if instructions:
        full_instructions = f"{_CONTENT_INSTRUCTIONS}\n\n{instructions}"
    result = await summarizer.summarize(transcript, instructions=full_instructions)

    if result.is_success:
        log.info("incident_summary_generated")
    else:
        log.warning(
            "incident_summary_failed",
            status=result.status,
            error=result.message,
        )
    return result


def _build_transcript(messages: Sequence[TranscriptMessage]) -> str:
    """Render messages as ``author: text`` lines in the given order."""
    return "\n".join(f"{message.author}: {message.text}" for message in messages)
