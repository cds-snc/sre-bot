"""Archive: close the incident through ``change_status``, announce it, archive its channel, then send one event.

``archive_incident`` serves ``/sre incident close`` and the stale notice's archive
button. The order is fixed: find the conversation's incident (a refusal writes
nothing and sends nothing), join the channel, set the status to Closed (the record
write is the commit point, decisions/incident-management.md), post the archived
notice, archive the channel, and send ``incident_channel_archived`` once, only after
a successful archive.

Joining is a step of the archive, never a gate: a channel the bot cannot join (a
private channel it left) still has its incident closed, and the notice and the
archive are skipped as ``not_joined``. A failed follower, notice or archive is
reported in its stage and never rolls the record back.
"""

from dataclasses import dataclass
from datetime import datetime

import structlog

from contracts.languages import MultilingualText
from contracts.operations import OperationResult
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.api import (
    ConversationReference,
    IncidentConversation,
    IncidentListProjection,
    IncidentReport,
    IncidentStore,
    find_incident_for_conversation,
)
from features.incident.response.interfaces import ArchivedEvent, ArchiveEventSink
from features.incident.response.service.status import StageOutcome, StageResult, StatusChange, change_status, stage_result

logger = structlog.get_logger()

_NOT_JOINED = StageResult(StageOutcome.SKIPPED, reason="not_joined")


@dataclass(frozen=True)
class Archive:
    """A committed archive: the status change and the join, notice and archive outcomes."""

    change: StatusChange
    join: StageResult
    notice: StageResult
    archive: StageResult


async def archive_incident(
    incidents: IncidentStore,
    reports: IncidentReport,
    projection: IncidentListProjection,
    conversations: IncidentConversation,
    events: ArchiveEventSink,
    conversation: ConversationReference,
    *,
    user_id: str,
    at: datetime,
    status_notice: str | MultilingualText,
    archived_notice: str | MultilingualText,
) -> OperationResult[Archive]:
    """Close the conversation's incident and archive the conversation.

    Args:
        incidents: The incident store; its status write is the commit point.
        reports: Writes the report's status line.
        projection: Writes the list row's status cell.
        conversations: Joins, posts to and archives the conversation.
        events: Receives the archived event after a successful archive.
        conversation: The conversation the command or button came from.
        user_id: The chat account that asked for the archive.
        at: When the archive is asked for.
        status_notice: The status-change text posted to the conversation, rendered by the caller.
        archived_notice: The archived text posted before the archive, rendered by the caller.

    Returns:
        The committed archive with each stage's outcome; the command check's
        refusal or the record write's failure, with nothing else written.

    Raises:
        ValueError: ``at`` is naive (``IncidentStore.set_status``).
    """
    found = await find_incident_for_conversation(incidents, conversation)
    if not found.is_success or found.data is None:
        return _failure(found)

    join = stage_result(await conversations.join(conversation))
    changed = await change_status(
        incidents, reports, projection, conversations, conversation, IncidentStatus.CLOSED, at=at, notice=status_notice
    )
    if not changed.is_success or changed.data is None:
        return _failure(changed)

    if join.outcome is StageOutcome.DONE:
        notice = stage_result(await conversations.post(conversation, archived_notice))
        archived = stage_result(await conversations.archive(conversation))
    else:
        notice = archived = _NOT_JOINED

    incident_id = changed.data.incident.id
    if archived.outcome is StageOutcome.DONE:
        await events.send_channel_archived(
            ArchivedEvent(incident_id=incident_id, conversation_id=conversation.vendor_id, user_id=user_id, at=at)
        )
    logger.info(
        "incident_archive_completed",
        incident_id=incident_id,
        join=join.outcome.value,
        notice=notice.outcome.value,
        archive=archived.outcome.value,
        join_error_code=join.error_code,
        archive_error_code=archived.error_code,
    )
    return OperationResult.success(Archive(change=changed.data, join=join, notice=notice, archive=archived))


def _failure[T](result: OperationResult[T]) -> OperationResult[Archive]:
    return OperationResult.error(
        status=result.status, message=result.message or "", error_code=result.error_code, retry_after=result.retry_after
    )
