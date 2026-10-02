"""Platform-agnostic incident-summary business logic.

Reads an incident conversation's transcript through the incident core
``IncidentTranscriptReader`` interface and delegates to the ``Summarizer``
interface (``integrations.openai``) to produce a catch-up summary for a
responder joining an incident channel.

This module is deliberately free of Slack and HTTP imports: it consumes
``TranscriptMessage`` values and returns an ``OperationResult`` so any
platform adapter can reuse it.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import structlog

from contracts.operations import OperationResult
from integrations.openai import Summarizer, get_summarizer
from packages.incident.core.api import IncidentTranscriptReader, TranscriptMessage, get_incident_transcript_reader
from packages.incident_summary.settings import IncidentSummarySettings, get_incident_summary_settings

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


async def summarize_incident_conversation(
    conversation_id: str,
    *,
    since: timedelta | None = None,
    limit: int | None = None,
    instructions: str | None = None,
    reader: IncidentTranscriptReader | None = None,
) -> OperationResult[str]:
    """Summarize what has been said in an incident conversation.

    Args:
        conversation_id: The incident conversation to summarize.
        since: How far back to read. When omitted the summary covers the whole
            incident, from the conversation's start, falling back to the
            configured default window when the start is unknown.
        limit: Maximum number of messages to read. Missing or not positive
            means the configured default; larger values are capped.
        instructions: Optional additional instructions passed on to
            ``summarize_transcript``.
        reader: Optional ``IncidentTranscriptReader``; defaults to the incident
            core's process singleton. Injected in tests.

    Returns:
        The ``OperationResult`` of ``summarize_transcript`` for the messages
        read, including its ``EMPTY_HISTORY`` error when nothing was read.
    """
    settings = get_incident_summary_settings()
    reader = reader or get_incident_transcript_reader()

    start = _resolve_window_start(reader, conversation_id, since, settings)
    messages = reader.read_transcript(conversation_id, since=start, limit=_resolve_limit(limit, settings))

    return await summarize_transcript(messages, instructions=instructions)


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
            prompt before being sent to the ``Summarizer`` interface.
        summarizer: Optional ``Summarizer`` interface; defaults to the process
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


def _resolve_limit(limit: int | None, settings: IncidentSummarySettings) -> int:
    """Turn the requested limit into a safe, capped message count."""
    if limit is None or limit <= 0:
        return settings.DEFAULT_HISTORY_LIMIT
    return min(limit, settings.MAX_HISTORY_LIMIT)


def _resolve_window_start(
    reader: IncidentTranscriptReader,
    conversation_id: str,
    since: timedelta | None,
    settings: IncidentSummarySettings,
) -> datetime:
    """Return the start of the window to summarize.

    An explicit ``since`` is measured from now. Without one the window starts
    when the conversation did, and falls back to the configured default window
    when the reader cannot say.
    """
    if since is not None:
        return _now() - since
    started_at = reader.conversation_started_at(conversation_id)
    if started_at is not None:
        return started_at
    return _now() - timedelta(hours=settings.DEFAULT_SINCE_HOURS)


def _now() -> datetime:
    """Return the current time, timezone-aware UTC."""
    return datetime.now(UTC)
