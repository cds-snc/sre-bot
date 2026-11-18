"""One conversation per incident: the create loop of decisions/incident-management.md.

Creating a conversation is a non-idempotent write whose idempotency mechanism is
the name. ``ensure_conversation`` applies the five rules: (1) an incident whose
record names a conversation never creates one; (2) each candidate name is claimed
for the incident before the call, and a name another incident holds is skipped;
(3) after any create that did not succeed, ``find_own`` comes first, and the bot's
own conversation bound to this incident, or unbound while this incident holds the
name, is reused; (4) the same name may always be retried, the next name only when
the conversation is proven another incident's or not the bot's; (5) an unknown
outcome with nothing found is reported without moving on.

A claimed name is completed at once with the incident id, so a retry of the same
incident sees its own claim. Completed claims expire (the coordination record
lifetime), so whose conversation it is is proven from its binding, never from the
claim alone. Declare uses it; attaching a conversation later (TASK-165.5) and the
rebind (TASK-165.11) reuse it.
"""

from collections.abc import Sequence

import structlog

from contracts.coordination import ClaimResult
from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from features.incident.core.api import (
    ConversationName,
    ConversationReference,
    Incident,
    IncidentConversation,
    IncidentStore,
    find_incident_for_conversation,
)
from features.incident.response.interfaces import Claims

logger = structlog.get_logger()


def name_claim_key(tenant: str, name: ConversationName) -> str:
    """The claim key of ``name`` in the chat tenant ``tenant``: ``incident:conversation_name:<tenant>:<name>``."""
    return f"incident:conversation_name:{tenant}:{name.prefix}-{name.title.strip().lower()}{name.suffix}"


async def ensure_conversation(
    incident: Incident,
    *,
    incidents: IncidentStore,
    conversations: IncidentConversation,
    claims: Claims,
    names: Sequence[ConversationName],
    tenant: str,
    private: bool = False,
) -> OperationResult[ConversationReference]:
    """Return the incident's conversation, creating it under the first name that is free or its own.

    Args:
        incident: The incident, as stored.
        incidents: Proves whose conversation a found one is, through its binding.
        conversations: Creates and finds the bot's own conversations.
        claims: Holds each candidate name for the incident.
        names: The candidate names, in order (``incident_conversation_names``).
        tenant: The chat tenant the names are claimed in.
        private: Whether a new conversation is private.

    Returns:
        The conversation (not yet attached: the caller attaches it), or a classified
        failure: an unknown create outcome with nothing found, a failed ``find_own``,
        or ``CONVERSATION_NAME_TAKEN`` once every name is another's.
    """
    if incident.conversation is not None:
        return OperationResult.success(incident.conversation)
    for name in names:
        if not await _hold(claims, tenant, name, incident.id):
            logger.info("incident_conversation_name_skipped", incident_id=incident.id, attempt=name.attempt)
            continue
        created = await _create(conversations, name, private=private, incident_id=incident.id)
        if created.is_success and created.data is not None:
            return OperationResult.success(created.data)
        found = await conversations.find_own(name)
        if not found.is_success:
            return _failed(found)
        if found.data is not None:
            owner = await find_incident_for_conversation(incidents, found.data)
            if owner.is_success and owner.data is not None and owner.data.id != incident.id:
                logger.info("incident_conversation_name_bound_elsewhere", incident_id=incident.id, attempt=name.attempt)
                continue
            if owner.is_success or owner.error_code == ErrorCode.NOT_AN_INCIDENT:
                logger.info("incident_conversation_reused", incident_id=incident.id, conversation_id=found.data.vendor_id)
                return OperationResult.success(found.data)
            return _failed(owner)
        if created.error_code == ErrorCode.CONVERSATION_NAME_TAKEN:
            logger.info("incident_conversation_name_taken", incident_id=incident.id, attempt=name.attempt)
            continue
        logger.warning(
            "incident_conversation_create_unknown",
            incident_id=incident.id,
            attempt=name.attempt,
            status=created.status.value,
            error_code=created.error_code,
        )
        return _failed(created)
    return OperationResult.permanent_error("Every candidate conversation name is taken", ErrorCode.CONVERSATION_NAME_TAKEN)


async def _hold(claims: Claims, tenant: str, name: ConversationName, incident_id: str) -> bool:
    """Claim ``name`` for the incident; True when it is (now or already) the incident's."""
    key = name_claim_key(tenant, name)
    outcome = await claims.claim(key)
    if outcome.result is ClaimResult.NEW and outcome.claim_token is not None:
        await claims.complete(key, {"incident_id": incident_id}, outcome.claim_token)
        return True
    if outcome.result is ClaimResult.COMPLETED:
        return (outcome.outcome or {}).get("incident_id") == incident_id
    return False


async def _create(
    conversations: IncidentConversation, name: ConversationName, *, private: bool, incident_id: str
) -> OperationResult[ConversationReference]:
    """One create attempt; an unclassified exception is an unknown outcome, logged with its traceback."""
    try:
        return await conversations.create(name, private=private)
    except Exception:
        logger.exception("incident_conversation_create_raised", incident_id=incident_id, attempt=name.attempt)
        return OperationResult.transient_error("The conversation create raised; its outcome is unknown")


def _failed[T](result: OperationResult[T]) -> OperationResult[ConversationReference]:
    return OperationResult.error(
        status=result.status,
        message=result.message or "",
        error_code=result.error_code,
        retry_after=result.retry_after,
    )
