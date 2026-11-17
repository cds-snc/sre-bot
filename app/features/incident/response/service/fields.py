"""Field update: the record first, then the notice in the record's conversation.

``update_fields`` writes the severity, the three times and the security flag the
update modal changes (entrypoints/slack_show.py); the status field goes through
``change_status`` instead, which also moves the report and the list.

The record write is the commit point (decisions/incident-management.md): a
refused command check or a failed record write returns that failure and posts
nothing. A lost guard is already re-read and recomputed once inside the store,
so nothing here retries (decisions/outbound-clients.md). The notice goes to the
record's conversation only when it is writable; a failed or skipped notice is
reported and never rolls the record back. Repeating a value writes no change and
posts the notice again.
"""

from dataclasses import dataclass
from datetime import datetime

import structlog

from contracts.operations import OperationResult
from features.incident.core.api import (
    ConversationReference,
    Incident,
    IncidentChanges,
    IncidentConversation,
    IncidentStore,
    find_incident_for_conversation,
)
from features.incident.response.service.status import StageOutcome, StageResult, channel_stage

logger = structlog.get_logger()


@dataclass(frozen=True)
class FieldsChange:
    """A committed field update: the incident as written, as it was before, and the notice's outcome."""

    incident: Incident
    previous: Incident
    channel: StageResult


async def update_fields(
    incidents: IncidentStore,
    conversations: IncidentConversation,
    conversation: ConversationReference,
    changes: IncidentChanges,
    *,
    by: str,
    at: datetime,
    notice: str,
) -> OperationResult[FieldsChange]:
    """Write ``changes`` to the conversation's incident, then post ``notice`` to its conversation.

    Args:
        incidents: The incident store; its write is the commit point.
        conversations: Checks and posts to the record's conversation.
        conversation: The conversation the modal was opened from.
        changes: The fields to write.
        by: Platform user id of who made the change; the severity entry's author.
        at: When the change is made.
        notice: The text posted to the record's conversation, rendered by the caller.

    Returns:
        The committed change with the notice's outcome; the command check's
        refusal or the record write's failure, with nothing posted.

    Raises:
        ValueError: ``by`` is blank or ``at`` is naive (``IncidentStore.update_fields``).
    """
    found = await find_incident_for_conversation(incidents, conversation)
    if not found.is_success or found.data is None:
        return OperationResult.error(
            status=found.status, message=found.message or "", error_code=found.error_code, retry_after=found.retry_after
        )
    log = logger.bind(incident_id=found.data.id, fields=sorted(changes.named()))

    written = await incidents.update_fields(found.data.id, changes, by=by, at=at)
    if not written.is_success or written.data is None:
        log.warning("incident_fields_record_write_failed", operation_status=written.status.value, error_code=written.error_code)
        return OperationResult.error(
            status=written.status, message=written.message or "", error_code=written.error_code, retry_after=written.retry_after
        )

    change = FieldsChange(
        incident=written.data, previous=found.data, channel=await channel_stage(conversations, written.data, notice)
    )
    if change.channel.outcome is StageOutcome.FAILED:
        log.warning(
            "incident_fields_stage_failed",
            stage="channel",
            operation_status=change.channel.status.value if change.channel.status else None,
            error_code=change.channel.error_code,
        )
    log.info("incident_fields_updated", channel=change.channel.outcome.value)
    return OperationResult.success(change)
