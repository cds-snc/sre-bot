"""Public surface of the incident core package.

Subdomains of the incident feature import this module and nothing else from
``core``: the interfaces every subdomain works on, their domain types, the
provider functions that resolve the default implementations, and
``find_incident_for_conversation``, the command check every incident command
applies first. ``StatusUpdateStore`` keeps each public status update as its own
record under the incident id.
"""

from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from typing import Protocol, runtime_checkable

from contracts.operations.result import OperationResult
from packages.incident.core.adapters.legacy_incidents import (
    build_legacy_incident_lookup,
    build_legacy_incident_security_reader,
)
from packages.incident.core.adapters.slack import build_incident_transcript_reader
from packages.incident.core.adapters.status_updates import build_status_update_store
from packages.incident.core.domain import (
    IncidentSecurityFlag,
    StatusUpdate,
    StatusUpdateStage,
    StatusUpdateState,
    StatusUpdateText,
    TranscriptMessage,
)

__all__ = [
    "IncidentLookup",
    "IncidentSecurityFlag",
    "IncidentSecurityReader",
    "IncidentTranscriptReader",
    "StatusUpdate",
    "StatusUpdateStage",
    "StatusUpdateState",
    "StatusUpdateStore",
    "StatusUpdateText",
    "TranscriptMessage",
    "find_incident_for_conversation",
    "get_incident_lookup",
    "get_incident_security_reader",
    "get_incident_transcript_reader",
    "get_status_update_store",
]


@runtime_checkable
class IncidentLookup(Protocol):
    """Interface resolving a conversation to the incident it belongs to."""

    def find_incident_for_conversation(self, conversation_id: str) -> OperationResult[str]:
        """Return the incident id for the conversation, or a classified refusal.

        Success carries the incident's id (the legacy UUID). A conversation
        that belongs to no incident is NOT_FOUND with ``NOT_AN_INCIDENT``; one
        that maps to several is PERMANENT_ERROR with
        ``AMBIGUOUS_INCIDENT_CONVERSATION``. A store failure is a classified
        error result, never an exception.
        """
        ...


@runtime_checkable
class IncidentSecurityReader(Protocol):
    """Interface reading whether an incident was declared as a security incident."""

    def read_security_flag(self, incident_id: str) -> OperationResult[IncidentSecurityFlag]:
        """Return the incident's security flag, or a classified refusal.

        Success carries YES, NO or UNKNOWN (never stored). An incident that does
        not exist (or a blank id) is NOT_FOUND with ``NOT_AN_INCIDENT``. A store
        failure is a classified error result with a generic message, never an
        exception and never NO.
        """
        ...


@runtime_checkable
class IncidentTranscriptReader(Protocol):
    """Interface reading what was said in an incident's conversation.

    Name resolution, ordering, time conversion and filtering happen behind the
    interface. Implementations never raise for a platform failure: they log it
    and return the documented empty value.
    """

    def conversation_started_at(self, conversation_id: str) -> datetime | None:
        """Return when the conversation started, timezone-aware UTC.

        Returns ``None`` when the platform cannot say (the lookup failed or the
        conversation carries no creation time); the caller applies its own
        fallback window.
        """
        ...

    def read_transcript(
        self,
        conversation_id: str,
        *,
        since: datetime,
        limit: int,
        exclude_own_and_system_messages: bool = False,
    ) -> Sequence[TranscriptMessage]:
        """Return the conversation's messages posted since ``since``, oldest first.

        Args:
            conversation_id: The conversation to read.
            since: Timezone-aware start of the window.
            limit: Maximum number of messages to fetch from the platform.
            exclude_own_and_system_messages: Drop this bot's own posts and the
                platform's system events (joins, topic changes and the like).

        Returns:
            The messages in chronological order; empty on a platform failure.
        """
        ...


@runtime_checkable
class StatusUpdateStore(Protocol):
    """Interface keeping an incident's public status updates, each its own record.

    Records live under the incident id, never on the incident item. Every
    write is a single conditional write, never a read-modify-write. A store
    failure is a classified error result, never an exception; a conflict is
    PERMANENT_ERROR with ``STATUS_UPDATE_CONFLICT``.
    """

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence.

        The caller numbers it: the latest update's sequence plus one, or 1.
        A different record already at that sequence is a conflict; the same
        record (a replay) is success.
        """
        ...

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update in one read; success with ``None`` when it has none."""
        ...

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        """Return every update of the incident, newest first."""
        ...

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        """Replace the stored update with ``update`` while its stored state is ``expected_state``.

        Used to approve (with the approver and edited text), to publish (with
        the time and the person) and to unpublish (clearing both). A
        stored state that moved on, or no stored record, is a conflict; the
        same write repeated is success.

        Raises:
            ValueError: ``expected_state`` cannot move to ``update.state``.
        """
        ...


@lru_cache(maxsize=1)
def get_incident_transcript_reader() -> IncidentTranscriptReader:
    """Return the process-wide Slack-backed ``IncidentTranscriptReader``."""
    return build_incident_transcript_reader()


@lru_cache(maxsize=1)
def get_incident_lookup() -> IncidentLookup:
    """Return the process-wide ``IncidentLookup`` over the legacy incidents table."""
    return build_legacy_incident_lookup()


@lru_cache(maxsize=1)
def get_incident_security_reader() -> IncidentSecurityReader:
    """Return the process-wide ``IncidentSecurityReader`` over the legacy incidents table."""
    return build_legacy_incident_security_reader()


def find_incident_for_conversation(conversation_id: str) -> OperationResult[str]:
    """Resolve the command's conversation to its incident id, or a classified refusal."""
    return get_incident_lookup().find_incident_for_conversation(conversation_id)


@lru_cache(maxsize=1)
def get_status_update_store() -> StatusUpdateStore:
    """Return the process-wide DynamoDB-backed ``StatusUpdateStore``."""
    return build_status_update_store()
