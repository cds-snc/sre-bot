"""Role assignment: the record first, then the role announcements and the channel purpose.

``assign_roles`` is the response subdomain's one roles engine: the roles modal's
submission calls it with the five roles the modal collected.

The record write (``IncidentStore.set_roles``, all five roles in one guarded
write) is the commit point (decisions/incident-management.md): a refused command
check or a failed record write returns that failure and writes nothing else.
The followers run after it, only when the incident's conversation is writable
(an archived channel never blocks the record): one announcement for each role
whose holder differs from what the modal showed, in role order, then the
purpose's ``IC: ... / OL: ...`` line. Each failure is logged and reported in its
stage and never rolls the record back. What the modal showed is the record's
roles, or for an incident with no role on the record the legacy report's
commander and lead (``read_incident_roles``).
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import structlog

from contracts.operations import OperationResult
from features.incident.common.vocabulary import IncidentRole
from features.incident.core.api import (
    ConversationReference,
    Incident,
    IncidentConversation,
    IncidentStore,
    LegacyRolesReader,
    conversation_is_writable,
    find_incident_for_conversation,
    read_incident_roles,
)
from features.incident.response.service.status import StageOutcome, StageResult, stage_result

logger = structlog.get_logger()

# Slack's limit on a channel purpose.
PURPOSE_MAX_LENGTH = 250

_ROLES_LINE = re.compile(r"IC: <@[\w]+> / OL: <@[\w]+>")
_DONE = StageResult(StageOutcome.DONE)


@dataclass(frozen=True)
class RolesChange:
    """A committed role assignment: the incident as written, the roles announced and each follower's outcome."""

    incident: Incident
    announced: tuple[IncidentRole, ...]
    announcements: StageResult
    purpose: StageResult


def purpose_with_roles(purpose: str, incident_commander: str, operations_lead: str) -> str:
    """Return ``purpose`` carrying the ``IC: <@..> / OL: <@..>`` line, cut to Slack's 250 characters.

    An existing line is replaced by a newline and the new one; a purpose without one gets
    it appended after a space and a newline, exactly as the legacy command wrote it.
    """
    line = f"\nIC: <@{incident_commander}> / OL: <@{operations_lead}>"
    updated = _ROLES_LINE.sub(lambda _: line, purpose) if _ROLES_LINE.search(purpose) else f"{purpose} {line}"
    return updated[:PURPOSE_MAX_LENGTH]


async def assign_roles(
    incidents: IncidentStore,
    conversations: IncidentConversation,
    legacy: LegacyRolesReader,
    conversation: ConversationReference,
    roles: Mapping[IncidentRole, str | None],
    *,
    announce: Callable[[IncidentRole, str], str],
) -> OperationResult[RolesChange]:
    """Give the conversation's incident the five ``roles``, then announce the changes and rewrite the purpose.

    Args:
        incidents: The incident store; its write is the commit point.
        conversations: Checks, posts to and rewrites the purpose of the record's conversation.
        legacy: Reads the roles a legacy incident carries on its report, for what the modal showed.
        conversation: The conversation the modal was opened from.
        roles: Each role's holder after the change; ``None`` unassigns it.
        announce: Renders the announcement of a role and its new holder, in the submitter's locale.

    Returns:
        The committed change with each follower's outcome; the command check's
        refusal or the record write's failure, with nothing else written.

    Raises:
        ValueError: A role is not an ``IncidentRole`` or a holder is blank (``IncidentStore.set_roles``).
    """
    found = await find_incident_for_conversation(incidents, conversation)
    if not found.is_success or found.data is None:
        return _failure(found)
    shown = await read_incident_roles(found.data, legacy)
    log = logger.bind(incident_id=found.data.id)

    written = await incidents.set_roles(found.data.id, roles)
    if not written.is_success or written.data is None:
        log.warning("incident_roles_record_write_failed", operation_status=written.status.value, error_code=written.error_code)
        return _failure(written)
    incident = written.data

    changed = tuple(
        (role, holder) for role in IncidentRole if (holder := roles.get(role)) is not None and holder != shown.get(role)
    )
    writable = await conversation_is_writable(conversations, incident.conversation)
    if not writable.is_success:
        announcements = purpose = stage_result(writable)
        announced: tuple[IncidentRole, ...] = ()
    elif not writable.data or incident.conversation is None:
        announcements = purpose = StageResult(StageOutcome.SKIPPED, reason="not_writable")
        announced = ()
    else:
        announced, announcements = await _announce(conversations, incident.conversation, changed, announce)
        purpose = await _purpose_stage(conversations, incident.conversation, incident)

    for name, stage in (("announcements", announcements), ("purpose", purpose)):
        if stage.outcome is StageOutcome.FAILED:
            log.warning(
                "incident_roles_stage_failed",
                stage=name,
                operation_status=stage.status.value if stage.status else None,
                error_code=stage.error_code,
            )
    log.info(
        "incident_roles_assigned",
        announced=[role.value for role in announced],
        announcements=announcements.outcome.value,
        purpose=purpose.outcome.value,
    )
    return OperationResult.success(RolesChange(incident, announced, announcements, purpose))


async def _announce(
    conversations: IncidentConversation,
    conversation: ConversationReference,
    changed: tuple[tuple[IncidentRole, str], ...],
    announce: Callable[[IncidentRole, str], str],
) -> tuple[tuple[IncidentRole, ...], StageResult]:
    """Post each changed role's announcement in role order; every post is tried and the first failure is reported."""
    announced: list[IncidentRole] = []
    failure = _DONE
    for role, holder in changed:
        posted = await conversations.post(conversation, announce(role, holder))
        if posted.is_success:
            announced.append(role)
        elif failure.outcome is not StageOutcome.FAILED:
            failure = stage_result(posted)
    return tuple(announced), failure


async def _purpose_stage(
    conversations: IncidentConversation, conversation: ConversationReference, incident: Incident
) -> StageResult:
    if incident.incident_commander is None or incident.operations_lead is None:
        return StageResult(StageOutcome.SKIPPED, reason="no_commander_or_lead")
    current = await conversations.purpose(conversation)
    if not current.is_success or current.data is None:
        return stage_result(current)
    updated = purpose_with_roles(current.data, incident.incident_commander, incident.operations_lead)
    return stage_result(await conversations.set_purpose(conversation, updated))


def _failure(result: OperationResult[Incident]) -> OperationResult[RolesChange]:
    return OperationResult.error(
        status=result.status, message=result.message or "", error_code=result.error_code, retry_after=result.retry_after
    )
