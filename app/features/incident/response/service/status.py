"""Status change: the record first, then the report status line, the list projection and the channel.

``change_status`` is the one status engine of the response subdomain: the slash
``status update`` command the archive (service/archive.py) and the update modal's
status field (entrypoints/slack_show.py) call it.

The record write is the commit point (decisions/incident-management.md): a
refused command check or a failed record write returns that failure and writes
nothing else. The followers (the report's status line, the list row's status
cell, the notice in the record's conversation) run in that order after it; each
failure is logged and reported in its stage and never rolls the record back,
and the next followers still run. Repeating a status writes no record change and
reruns every follower, which is how a failed follower is repaired. The notice
goes to the record's conversation, only when it is writable, so an archived
channel never blocks the record.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import structlog

from contracts.operations import OperationResult
from contracts.operations.status import OperationStatus
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.api import (
    ConversationReference,
    Incident,
    IncidentConversation,
    IncidentListProjection,
    IncidentReport,
    IncidentStore,
    conversation_is_writable,
    find_incident_for_conversation,
)

logger = structlog.get_logger()


class StageOutcome(StrEnum):
    """What happened to one follower write."""

    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class StageResult:
    """One follower write's outcome; a failure carries its classified status and code, a skip its reason."""

    outcome: StageOutcome
    status: OperationStatus | None = None
    error_code: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class StatusChange:
    """A committed status change: the incident as written, its previous status and each follower's outcome."""

    incident: Incident
    previous: IncidentStatus
    report: StageResult
    projection: StageResult
    channel: StageResult


_DONE = StageResult(StageOutcome.DONE)


async def change_status(
    incidents: IncidentStore,
    reports: IncidentReport,
    projection: IncidentListProjection,
    conversations: IncidentConversation,
    conversation: ConversationReference,
    status: IncidentStatus,
    *,
    at: datetime,
    notice: str,
) -> OperationResult[StatusChange]:
    """Set the status of the conversation's incident, then fan it out to the report, the list and the channel.

    Args:
        incidents: The incident store; its write is the commit point.
        reports: Writes the report's status line.
        projection: Writes the list row's status cell.
        conversations: Checks and posts to the record's conversation.
        conversation: The conversation the command came from.
        status: The new status.
        at: When the change is made; the opened time when it reopens the incident.
        notice: The text posted to the record's conversation, rendered by the caller.

    Returns:
        The committed change with each follower's outcome; the command check's
        refusal or the record write's failure, with nothing else written.

    Raises:
        ValueError: ``at`` is naive (``IncidentStore.set_status``).
    """
    found = await find_incident_for_conversation(incidents, conversation)
    if not found.is_success or found.data is None:
        return OperationResult.error(
            status=found.status, message=found.message or "", error_code=found.error_code, retry_after=found.retry_after
        )
    previous = found.data.status
    log = logger.bind(incident_id=found.data.id, status=status.value, previous=previous.value)

    written = await incidents.set_status(found.data.id, status, at=at)
    if not written.is_success or written.data is None:
        log.warning("incident_status_record_write_failed", operation_status=written.status.value, error_code=written.error_code)
        return OperationResult.error(
            status=written.status, message=written.message or "", error_code=written.error_code, retry_after=written.retry_after
        )
    incident = written.data

    change = StatusChange(
        incident=incident,
        previous=previous,
        report=await _report_stage(reports, incident, status),
        projection=stage_result(await projection.update_status(incident, status)),
        channel=await channel_stage(conversations, incident, notice),
    )
    for name, stage in (("report", change.report), ("projection", change.projection), ("channel", change.channel)):
        if stage.outcome is StageOutcome.FAILED:
            log.warning(
                "incident_status_stage_failed",
                stage=name,
                operation_status=stage.status.value if stage.status else None,
                error_code=stage.error_code,
            )
    log.info(
        "incident_status_changed",
        report=change.report.outcome.value,
        projection=change.projection.outcome.value,
        channel=change.channel.outcome.value,
    )
    return OperationResult.success(change)


async def _report_stage(reports: IncidentReport, incident: Incident, status: IncidentStatus) -> StageResult:
    if incident.report is None:
        return StageResult(StageOutcome.SKIPPED, reason="no_report")
    return stage_result(await reports.set_status_text(incident.report, status))


async def channel_stage(conversations: IncidentConversation, incident: Incident, notice: str) -> StageResult:
    """Post ``notice`` to the record's conversation when it is writable; skipped otherwise, never blocking the record."""
    writable = await conversation_is_writable(conversations, incident.conversation)
    if not writable.is_success:
        return stage_result(writable)
    if not writable.data or incident.conversation is None:
        return StageResult(StageOutcome.SKIPPED, reason="not_writable")
    return stage_result(await conversations.post(incident.conversation, notice))


def stage_result[T](result: OperationResult[T]) -> StageResult:
    """Map one write's result to its stage outcome: done, or failed with its status and code."""
    if result.is_success:
        return _DONE
    return StageResult(StageOutcome.FAILED, status=result.status, error_code=result.error_code)
