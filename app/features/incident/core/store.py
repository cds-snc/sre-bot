"""The incident store: the ``IncidentStore`` interface and its records-backed implementation.

``RecordIncidentStore`` reads the incidents table through the records contract
(``RecordStore``), never a cloud SDK. It reads end-state items only, those
carrying ``record_version``; an item without it is ``INCIDENT_RECORD_UNREADABLE``
until the legacy item bridge (TASK-145.5.8) upgrades it on read.

Production does not build this store yet: TASK-145.5.5 builds it from the
registry with the table name from the incident core settings.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

import structlog

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import KeySchema, RecordIndex, RecordQuery, RecordStore, RecordTable
from features.incident.core.adapters.incident_items import (
    incident_record_unreadable,
    parse_incident_item,
    read_reference,
)
from features.incident.core.domain import ConversationReference, Incident

logger = structlog.get_logger()

# Written on every end-state item; an item without it predates the end-state shape.
RECORD_VERSION = 1
# open_bucket value while an incident is open; the writers remove it on Closed.
OPEN_BUCKET = "OPEN"

# Far above any real count of incidents sharing one channel id; reaching it fails closed.
_CONVERSATION_QUERY_BOUND = 10
_STORE_FAILED_MESSAGE = "The incident store is unavailable."


def incidents_table(name: str) -> RecordTable:
    """Return the incidents table declaration; the index names match terraform/dynamodb.tf."""
    return RecordTable(
        name=name,
        key=KeySchema(partition="id"),
        indexes={
            "by_channel": RecordIndex(physical_name="by_channel", key=KeySchema(partition="channel_id")),
            "open": RecordIndex(physical_name="open", key=KeySchema(partition="open_bucket", sort="opened_at")),
        },
    )


@runtime_checkable
class IncidentStore(Protocol):
    """Interface reading the incident record.

    Every method returns an ``OperationResult``: an incident that does not
    exist (or a blank id) is NOT_FOUND with ``NOT_AN_INCIDENT``; a stored item
    that cannot be read is PERMANENT_ERROR with ``INCIDENT_RECORD_UNREADABLE``;
    a store failure carries the store's status, error code and retry hint with a
    generic message. Nothing raises.

    Writes arrive with their slices: create with TASK-145.7, update with
    TASK-145.8 and the timeline append with TASK-145.9.
    """

    def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the incident with this id."""
        ...

    def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        """Return the one incident whose conversation is ``conversation``.

        Only incidents of the same system and tenant count, since two tenants
        can share one conversation id. Several matches are PERMANENT_ERROR
        with ``AMBIGUOUS_INCIDENT_CONVERSATION``.
        """
        ...

    def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return every open incident, oldest first by when it was opened."""
        ...

    def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return whether the incident was declared as a security incident; a failure is never false."""
        ...


class RecordIncidentStore(IncidentStore):
    """Read incidents from the incidents table through the records contract."""

    def __init__(self, records: RecordStore, table: RecordTable) -> None:
        self._records = records
        self._table = table

    def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the incident with this id."""
        if not incident_id.strip():
            return no_such_incident()
        result = self._records.get(self._table, {"id": incident_id})
        if result.status is OperationStatus.NOT_FOUND:
            return no_such_incident()
        if not result.is_success:
            return self._failed(result, operation="get")
        item: Mapping[str, Any] = result.data or {}
        return self._parse(item, operation="get")

    def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        """Return the one incident whose conversation is ``conversation``.

        Queries the by_channel index with a small bound; index reads return full
        items. A candidate of another system or tenant, or with an unreadable
        conversation, is skipped before parsing. A candidate without
        ``record_version`` cannot be checked, so the lookup fails closed. A full
        page means more may exist, so it is ambiguous; there is no fallback read.
        """
        if not conversation.vendor_id.strip():
            return not_an_incident()
        operation = "find_by_conversation"
        result = self._records.query(
            self._table,
            RecordQuery(partition=conversation.vendor_id, index="by_channel", limit=_CONVERSATION_QUERY_BOUND),
        )
        if not result.is_success:
            return self._failed(result, operation=operation)
        candidates: list[Mapping[str, Any]] = result.data or []
        if len(candidates) >= _CONVERSATION_QUERY_BOUND:
            return ambiguous_conversation(conversation, match_count=len(candidates))
        matches = []
        for item in candidates:
            if not _is_end_state(item, operation=operation):
                return incident_record_unreadable()
            stored = read_reference(item, "conversation", ConversationReference, item.get("id"))
            if stored is not None and (stored.system, stored.tenant) == (conversation.system, conversation.tenant):
                matches.append(item)
        if not matches:
            return not_an_incident()
        if len(matches) > 1:
            return ambiguous_conversation(conversation, match_count=len(matches))
        return self._parse(matches[0], operation=operation)

    def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return every incident carrying open_bucket, oldest first by opened_at.

        One unreadable item fails the whole read: a partial list would hide an
        open incident.
        """
        result = self._records.query(self._table, RecordQuery(partition=OPEN_BUCKET, index="open"))
        if not result.is_success:
            return self._failed(result, operation="list_open")
        incidents: list[Incident] = []
        for item in result.data or []:
            parsed = self._parse(item, operation="list_open")
            if parsed.data is None:
                return _refusal(parsed)
            incidents.append(parsed.data)
        return OperationResult.success(data=incidents)

    def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return the incident's stored security flag, read with the whole record."""
        incident = self.get(incident_id)
        if incident.data is None:
            return _refusal(incident)
        return OperationResult.success(data=incident.data.security_incident)

    def _parse(self, item: Mapping[str, Any], *, operation: str) -> OperationResult[Incident]:
        if not _is_end_state(item, operation=operation):
            return incident_record_unreadable()
        return parse_incident_item(item)

    def _failed[T](self, result: OperationResult[Any], *, operation: str) -> OperationResult[T]:
        status = result.status
        if status is OperationStatus.NOT_FOUND:
            # A missing table or index is a broken store; NOT_FOUND is reserved for "not an incident".
            status = OperationStatus.PERMANENT_ERROR
        logger.warning(
            "incident_store_failed",
            operation=operation,
            table=self._table.name,
            status=status.value,
            error_code=result.error_code,
        )
        return OperationResult.error(
            status, message=_STORE_FAILED_MESSAGE, error_code=result.error_code, retry_after=result.retry_after
        )


def _refusal[T](result: OperationResult[Any]) -> OperationResult[T]:
    """Carry a refusal over to another result type; it holds no data."""
    return OperationResult.error(
        result.status, message=result.message or "", error_code=result.error_code, retry_after=result.retry_after
    )


def _is_end_state(item: Mapping[str, Any], *, operation: str) -> bool:
    if item.get("record_version") is not None:
        return True
    logger.warning("incident_item_not_upgraded", operation=operation, incident_id=item.get("id"))
    return False


def not_an_incident[T]() -> OperationResult[T]:
    """Return the refusal for a conversation that belongs to no incident."""
    return OperationResult.error(
        OperationStatus.NOT_FOUND, message="No incident is recorded for this conversation.", error_code=ErrorCode.NOT_AN_INCIDENT
    )


def no_such_incident[T]() -> OperationResult[T]:
    """Return the refusal for an incident id that names no incident."""
    return OperationResult.error(
        OperationStatus.NOT_FOUND, message="No such incident is recorded.", error_code=ErrorCode.NOT_AN_INCIDENT
    )


def ambiguous_conversation[T](conversation: ConversationReference, *, match_count: int) -> OperationResult[T]:
    """Return the refusal for a conversation recorded on more than one incident."""
    logger.warning(
        "incident_conversation_ambiguous",
        system=conversation.system.value,
        tenant=conversation.tenant,
        conversation_id=conversation.vendor_id,
        match_count=match_count,
    )
    return OperationResult.error(
        OperationStatus.PERMANENT_ERROR,
        message="More than one incident is recorded for this conversation.",
        error_code=ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION,
    )
