"""The incident core stores: their interfaces and records-backed implementations.

``RecordIncidentStore`` reads the incidents table through the records contract
(``RecordStore``), never a cloud SDK. An item carrying ``record_version`` is
parsed as stored; an item without it is upgraded on read by the legacy item
bridge (``adapters/legacy_items.py``) with the configured tenants, and is
``INCIDENT_RECORD_UNREADABLE`` when the bridge cannot read it.

``RecordStatusUpdateStore`` keeps each public status update as its own item in
the status-updates table, in the layout of ``adapters/status_updates.py``.

Entry points build both per service scope with ``build_incident_store`` and
``build_status_update_store`` in ``core/api.py``, from the resolved
``RecordStore`` and the incident core settings.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

import structlog

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import (
    KeySchema,
    RecordChange,
    RecordIndex,
    RecordQuery,
    RecordStore,
    RecordTable,
    RemoveAttribute,
    SetAttribute,
    SortCondition,
    SortOperator,
    SortOrder,
)
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.incident_items import (
    incident_record_unreadable,
    parse_incident_item,
    read_reference,
)
from features.incident.core.adapters.legacy_items import UnreadableLegacyItem, upgrade_legacy_item
from features.incident.core.adapters.status_updates import (
    OPTIONAL_ATTRIBUTES,
    PARTITION_ATTRIBUTE,
    SORT_ATTRIBUTE,
    SORT_KEY_PREFIX,
    UnreadableStatusUpdateItemError,
    parse_status_update_item,
    partition_key,
    status_update_item,
    status_update_key,
)
from features.incident.core.domain import ConversationReference, Incident, StatusUpdate, StatusUpdateState

logger = structlog.get_logger()

# Written on every end-state item; an item without it predates the end-state shape.
RECORD_VERSION = 1
# open_bucket value while an incident is open; the writers remove it on Closed.
OPEN_BUCKET = "OPEN"

# Far above any real count of incidents sharing one channel id; reaching it fails closed.
_CONVERSATION_QUERY_BOUND = 10
_STORE_FAILED_MESSAGE = "The incident store is unavailable."
_STATUS_UPDATE_STORE_FAILED_MESSAGE = "The status update store is unavailable."
_STATUS_UPDATE_CONFLICT_MESSAGE = "The status update was changed or taken by another writer."
_STATUS_UPDATE_UNREADABLE_MESSAGE = "A stored status update could not be read."


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


def status_updates_table(name: str) -> RecordTable:
    """Return the status-updates table declaration; the keys match terraform/dynamodb.tf."""
    return RecordTable(name=name, key=KeySchema(partition=PARTITION_ATTRIBUTE, sort=SORT_ATTRIBUTE))


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
    """Read incidents from the incidents table through the records contract.

    ``tenants`` is the configured tenant per workplace system, which the legacy
    item bridge gives the references of items without ``record_version``.
    """

    def __init__(self, records: RecordStore, table: RecordTable, tenants: Mapping[WorkplaceSystem, str]) -> None:
        self._records = records
        self._table = table
        self._tenants = tenants

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
        conversation, is skipped before parsing; a legacy candidate is upgraded
        first. A candidate that cannot be read cannot be checked, so the lookup
        fails closed. A full
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
        for candidate in candidates:
            item = self._end_state(candidate, operation=operation)
            if item is None:
                return incident_record_unreadable()
            stored = read_reference(item, "conversation", ConversationReference, item.get("id"))
            if stored is not None and (stored.system, stored.tenant) == (conversation.system, conversation.tenant):
                matches.append(item)
        if not matches:
            return not_an_incident()
        if len(matches) > 1:
            return ambiguous_conversation(conversation, match_count=len(matches))
        return parse_incident_item(matches[0])

    def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return every incident carrying open_bucket, oldest first by opened_at.

        Legacy items carry open_bucket only once the legacy upgrade job
        (TASK-145.5.7) has run. One unreadable item fails the whole read: a partial list would hide an
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
        end_state = self._end_state(item, operation=operation)
        if end_state is None:
            return incident_record_unreadable()
        return parse_incident_item(end_state)

    def _end_state(self, item: Mapping[str, Any], *, operation: str) -> Mapping[str, Any] | None:
        """Return the item in the end-state shape, upgrading a legacy one; ``None`` when it cannot be read."""
        if item.get("record_version") is not None:
            return item
        upgraded = upgrade_legacy_item(item, self._tenants)
        if isinstance(upgraded, UnreadableLegacyItem):
            # The value is logged for status only: other legacy values may be vendor links.
            log_fields: dict[str, object] = {
                "operation": operation,
                "incident_id": upgraded.incident_id,
                "field": upgraded.field,
            }
            if upgraded.field == "status":
                log_fields["value"] = upgraded.value
            logger.warning("incident_record_unreadable", **log_fields)
            return None
        return upgraded.item

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


@runtime_checkable
class StatusUpdateStore(Protocol):
    """Interface keeping an incident's public status updates, each its own record.

    Records live under the incident id, never on the incident item. Every
    write is a single conditional write, never a read-modify-write. A store
    failure is a classified error result, never an exception; a conflict is
    PERMANENT_ERROR with ``STATUS_UPDATE_CONFLICT``. A write whose condition no
    longer holds is a conflict also when it repeats a write that already
    landed; a store resolves only its own SDK retry. The caller that needs to
    tell its own write from another writer's re-reads once.
    """

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence.

        The caller numbers it: the latest update's sequence plus one, or 1.
        Any record already at that sequence is a conflict.
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
        the time and the person) and to unpublish (clearing both). A stored
        state that moved on, or no stored record, is a conflict.

        Raises:
            ValueError: ``expected_state`` cannot move to ``update.state``.
        """
        ...


class RecordStatusUpdateStore(StatusUpdateStore):
    """Keep status updates in the status-updates table through the records contract."""

    def __init__(self, records: RecordStore, table: RecordTable) -> None:
        self._records = records
        self._table = table

    def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Create the update's item only where none exists."""
        result = self._records.put_if_not_exists(self._table, status_update_item(update))
        if not result.is_success:
            return self._failed(result, operation="append", incident_id=update.incident_id)
        if result.data is not True:
            return self._conflict(update, operation="append")
        return OperationResult.success(data=update)

    def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        """Rewrite the update's attributes in one update guarded on the stored state.

        Raises:
            ValueError: ``expected_state`` cannot move to ``update.state``.
        """
        if not expected_state.can_move_to(update.state):
            raise ValueError(f"no status update transition from {expected_state} to {update.state}")
        item = status_update_item(update)
        key = status_update_key(update.incident_id, update.sequence)
        changes: list[RecordChange] = [SetAttribute(name, value) for name, value in item.items() if name not in key]
        changes += [RemoveAttribute(name) for name in OPTIONAL_ATTRIBUTES if name not in item]
        result = self._records.update(self._table, key, changes, expected={"state": expected_state.value})
        # A missing item is NOT_FOUND without an error code; a missing table carries the backend's code.
        missing_item = result.status is OperationStatus.NOT_FOUND and result.error_code is None
        if missing_item or (result.is_success and result.data is None):
            return self._conflict(update, operation="transition")
        if not result.is_success:
            return self._failed(result, operation="transition", incident_id=update.incident_id)
        return OperationResult.success(data=update)

    def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update, or success with ``None`` when it has none."""
        updates = self._query(incident_id, operation="latest", limit=1)
        if updates.data is None:
            return _refusal(updates)
        return OperationResult.success(data=updates.data[0] if updates.data else None)

    def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        """Return every update of the incident, newest first."""
        return self._query(incident_id, operation="list_for_incident", limit=None)

    def _query(self, incident_id: str, *, operation: str, limit: int | None) -> OperationResult[Sequence[StatusUpdate]]:
        spec = RecordQuery(
            partition=partition_key(incident_id),
            sort=SortCondition(SortOperator.BEGINS_WITH, SORT_KEY_PREFIX),
            limit=limit,
            order=SortOrder.DESC,
        )
        result = self._records.query(self._table, spec)
        if not result.is_success:
            return self._failed(result, operation=operation, incident_id=incident_id)
        try:
            return OperationResult.success(data=tuple(parse_status_update_item(item) for item in result.data or []))
        except UnreadableStatusUpdateItemError as exc:
            logger.error(
                "status_update_unreadable",
                operation=operation,
                table=self._table.name,
                incident_id=incident_id,
                reason=str(exc),
            )
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=_STATUS_UPDATE_UNREADABLE_MESSAGE,
                error_code=ErrorCode.STATUS_UPDATE_UNREADABLE,
            )

    def _conflict[T](self, update: StatusUpdate, *, operation: str) -> OperationResult[T]:
        logger.info(
            "status_update_conflict",
            operation=operation,
            table=self._table.name,
            incident_id=update.incident_id,
            sequence=update.sequence,
        )
        return OperationResult.error(
            OperationStatus.PERMANENT_ERROR,
            message=_STATUS_UPDATE_CONFLICT_MESSAGE,
            error_code=ErrorCode.STATUS_UPDATE_CONFLICT,
        )

    def _failed[T](self, result: OperationResult[Any], *, operation: str, incident_id: str) -> OperationResult[T]:
        status = result.status
        if status is OperationStatus.NOT_FOUND:
            # A missing table is a broken store, not an incident without updates.
            status = OperationStatus.PERMANENT_ERROR
        logger.warning(
            "status_update_store_failed",
            operation=operation,
            table=self._table.name,
            incident_id=incident_id,
            status=status.value,
            error_code=result.error_code,
        )
        return OperationResult.error(
            status,
            message=_STATUS_UPDATE_STORE_FAILED_MESSAGE,
            error_code=result.error_code,
            retry_after=result.retry_after,
        )
