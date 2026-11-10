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
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.binding_items import (
    CONVERSATION_ATTRIBUTE,
    UnknownBindingKindError,
    UnreadableBindingItemError,
    binding_item,
    parse_binding_item,
)
from features.incident.core.adapters.binding_items import (
    PARTITION_ATTRIBUTE as BINDING_PARTITION_ATTRIBUTE,
)
from features.incident.core.adapters.binding_items import (
    SORT_ATTRIBUTE as BINDING_SORT_ATTRIBUTE,
)
from features.incident.core.adapters.incident_items import (
    OPEN_BUCKET,
    RECORD_VERSION,
    incident_item,
    incident_record_unreadable,
    parse_incident_item,
    read_reference,
    reference_item,
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
from features.incident.core.domain import (
    BindingKind,
    ConversationReference,
    ExternalCaseReference,
    Incident,
    IncidentBinding,
    PostmortemMeetingReference,
    ReferenceKind,
    ReportReference,
    ResourceReference,
    StatusUpdate,
    StatusUpdateState,
    VideoCallReference,
)

logger = structlog.get_logger()

# Far above any real count of incidents sharing one channel id; reaching it fails closed.
_CONVERSATION_QUERY_BOUND = 10
_STORE_FAILED_MESSAGE = "The incident store is unavailable."
_RECORD_CONFLICT_MESSAGE = "The incident record is not in the shape this writer owns."
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


def bindings_table(name: str) -> RecordTable:
    """Return the bindings table declaration; the keys and index match terraform/dynamodb.tf."""
    return RecordTable(
        name=name,
        key=KeySchema(partition=BINDING_PARTITION_ATTRIBUTE, sort=BINDING_SORT_ATTRIBUTE),
        indexes={
            "by_conversation": RecordIndex(physical_name="by_conversation", key=KeySchema(partition=CONVERSATION_ATTRIBUTE))
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
    generic message. Only a caller error raises (``ValueError``, nothing written).

    Writes arrive with their slices: create and set_reference with TASK-145.7,
    the field updates with TASK-145.8 and the timeline append with TASK-145.9.
    """

    def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the incident with this id."""
        ...

    def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        """Return the one incident whose conversation is ``conversation``.

        The incident's active bindings are read first; only when none names an
        incident that exists does the lookup read the incident records' own
        conversation. The two sources are never merged. Only incidents of the
        same system and tenant count, since two tenants can share one
        conversation id. Several matches are PERMANENT_ERROR with
        ``AMBIGUOUS_INCIDENT_CONVERSATION``.
        """
        ...

    def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return every open incident, oldest first by when it was opened."""
        ...

    def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return whether the incident was declared as a security incident; a failure is never false."""
        ...

    def create(self, incident: Incident, binding: IncidentBinding) -> OperationResult[Incident]:
        """Store a new open incident: its primary chat binding first, then its record, the commit point.

        Idempotent on ``incident.id``: a retry with the same id stores each item
        once, and a replay where the record exists writes nothing and returns the
        stored incident. A failed record write leaves a binding no lookup returns.

        Raises:
            ValueError: ``incident`` is not open or has no conversation, or
                ``binding`` is not its active primary chat binding on that conversation.
        """
        ...

    def set_reference(self, incident_id: str, kind: ReferenceKind, reference: ResourceReference) -> OperationResult[Incident]:
        """Replace the incident's reference of ``kind`` whole and return the updated incident.

        Only an end-state record of the current version is changed; any other
        is PERMANENT_ERROR with ``INCIDENT_RECORD_CONFLICT``. Repeating it is a no-op.

        Raises:
            ValueError: ``reference`` is not the reference type of ``kind``.
        """
        ...


class RecordIncidentStore(IncidentStore):
    """Read incidents from the incidents table through the records contract.

    ``tenants`` is the configured tenant per workplace system, which the legacy
    item bridge gives the references of items without ``record_version``.
    ``bindings`` is the bindings table ``find_by_conversation`` reads first; it
    has no default, so no construction can skip it.
    """

    def __init__(
        self,
        records: RecordStore,
        table: RecordTable,
        tenants: Mapping[WorkplaceSystem, str],
        *,
        bindings: RecordTable,
    ) -> None:
        self._records = records
        self._table = table
        self._tenants = tenants
        self._bindings = bindings

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

        Queries the bindings table's by_conversation index with a small bound;
        a binding of an unknown kind is skipped and logged, an unreadable one of
        a known kind fails the lookup closed, a full page is ambiguous. The
        active bindings of the same system and tenant name incident records,
        which are read; a binding whose record is missing is dropped. No live
        binding falls back to the by_channel read of the incidents table, one
        is the answer, several are ambiguous. A bindings-table failure is a
        classified failure with no fallback.
        """
        if not conversation.vendor_id.strip():
            return not_an_incident()
        operation = "find_by_conversation"
        result = self._records.query(
            self._bindings,
            RecordQuery(partition=conversation.vendor_id, index="by_conversation", limit=_CONVERSATION_QUERY_BOUND),
        )
        if not result.is_success:
            return self._failed(result, operation=operation, table=self._bindings)
        rows: list[Mapping[str, Any]] = result.data or []
        if len(rows) >= _CONVERSATION_QUERY_BOUND:
            return ambiguous_conversation(conversation, match_count=len(rows))
        bindings: list[IncidentBinding] = []
        for row in rows:
            try:
                bindings.append(parse_binding_item(row))
            except UnknownBindingKindError as unknown:
                logger.warning("incident_binding_unknown_kind", incident_id=unknown.incident_id, kind=unknown.kind)
            except UnreadableBindingItemError as unreadable:
                logger.warning("incident_binding_unreadable", incident_id=unreadable.incident_id, field=unreadable.field)
                return incident_record_unreadable()
        live: list[Incident] = []
        for binding in select_active_bindings(conversation, bindings):
            read = self.get(binding.incident_id)
            if read.data is not None:
                live.append(read.data)
            elif read.status is not OperationStatus.NOT_FOUND:
                return read
        if not live:
            return self._find_by_channel(conversation, operation=operation)
        if len(live) > 1:
            return ambiguous_conversation(conversation, match_count=len(live))
        return OperationResult.success(data=live[0])

    def _find_by_channel(self, conversation: ConversationReference, *, operation: str) -> OperationResult[Incident]:
        """Return the incident whose own record names ``conversation``, read from the by_channel index.

        Index reads return full items. A candidate of another system or tenant
        is skipped before parsing and logged as a warning naming both tenants;
        one with an unreadable conversation is skipped; a legacy candidate is
        upgraded first. A candidate that cannot be read cannot be checked, so
        the lookup fails closed. A full page means more may exist, so it is
        ambiguous; there is no fallback read.
        """
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
            if stored is None:
                continue
            if (stored.system, stored.tenant) == (conversation.system, conversation.tenant):
                matches.append(item)
            else:
                # Never the vendor id: the channel id is the query key the caller already holds.
                logger.warning(
                    "incident_conversation_candidate_dropped",
                    incident_id=item.get("id"),
                    stored_system=stored.system.value,
                    stored_tenant=stored.tenant,
                    requested_system=conversation.system.value,
                    requested_tenant=conversation.tenant,
                )
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

    def create(self, incident: Incident, binding: IncidentBinding) -> OperationResult[Incident]:
        """Put the binding, then the record, each only where nothing is stored.

        A binding already stored under its key is this incident's own from an
        earlier attempt. A record already stored under the id is a replay: nothing
        is rewritten and the stored incident is returned.

        Raises:
            ValueError: see ``IncidentStore.create``.
        """
        validate_new_incident(incident, binding)
        bound = self._records.put_if_not_exists(self._bindings, binding_item(binding))
        if not bound.is_success:
            return self._failed(bound, operation="create", table=self._bindings)
        stored = self._records.put_if_not_exists(self._table, incident_item(incident))
        if not stored.is_success:
            return self._failed(stored, operation="create")
        if stored.data is not True:
            logger.info("incident_create_replayed", incident_id=incident.id)
            return self.get(incident.id)
        return OperationResult.success(data=incident)

    def set_reference(self, incident_id: str, kind: ReferenceKind, reference: ResourceReference) -> OperationResult[Incident]:
        """Set the reference map in one update guarded on ``record_version``.

        Raises:
            ValueError: see ``IncidentStore.set_reference``.
        """
        validate_reference(kind, reference)
        if not incident_id.strip():
            return no_such_incident()
        result = self._records.update(
            self._table,
            {"id": incident_id},
            [SetAttribute(kind.value, reference_item(reference))],
            expected={"record_version": RECORD_VERSION},
        )
        # A missing item is NOT_FOUND without an error code; a missing table carries the backend's code.
        if result.status is OperationStatus.NOT_FOUND and result.error_code is None:
            return no_such_incident()
        if not result.is_success:
            return self._failed(result, operation="set_reference")
        if result.data is None:
            logger.warning("incident_record_conflict", operation="set_reference", incident_id=incident_id, kind=kind.value)
            return record_conflict()
        return self._parse(result.data, operation="set_reference")

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

    def _failed[T](self, result: OperationResult[Any], *, operation: str, table: RecordTable | None = None) -> OperationResult[T]:
        status = result.status
        if status is OperationStatus.NOT_FOUND:
            # A missing table or index is a broken store; NOT_FOUND is reserved for "not an incident".
            status = OperationStatus.PERMANENT_ERROR
        logger.warning(
            "incident_store_failed",
            operation=operation,
            table=(self._table if table is None else table).name,
            status=status.value,
            error_code=result.error_code,
        )
        return OperationResult.error(
            status, message=_STORE_FAILED_MESSAGE, error_code=result.error_code, retry_after=result.retry_after
        )


def select_active_bindings(conversation: ConversationReference, bindings: Sequence[IncidentBinding]) -> list[IncidentBinding]:
    """Return the bindings that count for ``conversation``: not archived, and of its system and tenant.

    A binding of another system or tenant is dropped with a warning naming both
    tenants (never the conversation id, which the caller already holds). Shared
    by the real store and the in-memory fake so their classification cannot drift.
    """
    active: list[IncidentBinding] = []
    for binding in bindings:
        if binding.archived_at is not None:
            continue
        if (binding.system, binding.tenant) != (conversation.system, conversation.tenant):
            logger.warning(
                "incident_conversation_candidate_dropped",
                incident_id=binding.incident_id,
                stored_system=binding.system.value,
                stored_tenant=binding.tenant,
                requested_system=conversation.system.value,
                requested_tenant=conversation.tenant,
                source="binding",
            )
            continue
        active.append(binding)
    return active


def validate_new_incident(incident: Incident, binding: IncidentBinding) -> None:
    """Refuse a create the record could not honour; shared by the real store and the fake.

    Raises:
        ValueError: ``incident`` is not open or has no conversation, or
            ``binding`` is not its active primary chat binding on that conversation.
    """
    if incident.status is not IncidentStatus.OPEN:
        raise ValueError(f"a created incident must be open, got {incident.status}")
    if incident.conversation is None:
        raise ValueError("a created incident needs its conversation")
    if binding.incident_id != incident.id:
        raise ValueError("binding.incident_id must be the created incident's id")
    if binding.kind is not BindingKind.CHAT_CONVERSATION:
        raise ValueError(f"a created incident's binding must be its chat conversation, got {binding.kind}")
    if not binding.primary:
        raise ValueError("a created incident's binding must be primary")
    if binding.archived_at is not None:
        raise ValueError("a created incident's binding must not be archived")
    conversation = incident.conversation
    if (binding.system, binding.tenant, binding.vendor_id) != (conversation.system, conversation.tenant, conversation.vendor_id):
        raise ValueError("the binding must name the incident's conversation")


def validate_reference(kind: ReferenceKind, reference: ResourceReference) -> None:
    """Refuse a reference that is not the type of ``kind``; shared by the real store and the fake.

    Raises:
        ValueError: ``reference`` is not exactly the reference type the record holds for ``kind``.
    """
    expected = _REFERENCE_TYPES[kind]
    if type(reference) is not expected:
        raise ValueError(f"{kind.value} takes a {expected.__name__}, got {type(reference).__name__}")


_REFERENCE_TYPES: dict[ReferenceKind, type[ResourceReference]] = {
    ReferenceKind.REPORT: ReportReference,
    ReferenceKind.VIDEO_CALL: VideoCallReference,
    ReferenceKind.POSTMORTEM_MEETING: PostmortemMeetingReference,
    ReferenceKind.EXTERNAL_CASE: ExternalCaseReference,
}


def record_conflict[T]() -> OperationResult[T]:
    """Return the refusal for a record that is not the end-state version this writer owns."""
    return OperationResult.error(
        OperationStatus.PERMANENT_ERROR, message=_RECORD_CONFLICT_MESSAGE, error_code=ErrorCode.INCIDENT_RECORD_CONFLICT
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
