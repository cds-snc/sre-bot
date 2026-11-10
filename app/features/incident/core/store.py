"""The incident core stores: their interfaces and records-backed implementations.

``RecordIncidentStore`` reads the incidents table through the records contract
(``RecordStore``), never a cloud SDK. An item carrying ``record_version`` is
parsed as stored; an item without it is upgraded on read by the legacy item
bridge (``adapters/legacy_items.py``) with the configured tenants, and is
``INCIDENT_RECORD_UNREADABLE`` when the bridge cannot read it.

Field writes (``update_fields``, ``set_roles``, ``set_status``) are guarded on
``record_version`` and on the read value of every attribute they change. An
item below the current version is upgraded on write: ``plan_item_upgrade``, the
legacy upgrade job's plan, gives its binding (put first) and its changes, which
go out in the one update that carries the field change.

``RecordTimelineStore`` keeps each timeline entry as its own item in the
timeline table, in the layout of ``adapters/timeline_items.py``.
``RecordStatusUpdateStore`` keeps each public status update as its own item in
the status-updates table, in the layout of ``adapters/status_updates.py``.

Both stores are async: each Record adapter runs a call's blocking ``RecordStore`` work in one
``asyncio.to_thread``; the timeline store stays sync, since only the incident store's thread calls it.

Entry points build the incident and status-update stores per service scope with ``build_incident_store`` and
``build_status_update_store`` in ``core/api.py``, from the resolved
``RecordStore`` and the incident core settings.
"""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, fields, replace
from datetime import datetime
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
from features.incident.common.vocabulary import IncidentRole, IncidentStatus
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
    format_stored_time,
    incident_item,
    incident_record_unreadable,
    parse_incident_item,
    read_reference,
    reference_item,
)
from features.incident.core.adapters.item_upgrade import (
    ItemUpgrade,
    UnboundOpenItem,
    UnguardableValueError,
    guard_value,
    plan_item_upgrade,
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
from features.incident.core.adapters.timeline_items import (
    PARTITION_ATTRIBUTE as TIMELINE_PARTITION_ATTRIBUTE,
)
from features.incident.core.adapters.timeline_items import (
    SORT_ATTRIBUTE as TIMELINE_SORT_ATTRIBUTE,
)
from features.incident.core.adapters.timeline_items import severity_entry_id, timeline_entry_item
from features.incident.core.domain import (
    BindingKind,
    ConversationReference,
    ExternalCaseReference,
    Incident,
    IncidentBinding,
    IncidentChanges,
    PostmortemMeetingReference,
    ReferenceKind,
    ReportReference,
    ResourceReference,
    SeverityChange,
    StatusUpdate,
    StatusUpdateState,
    TimelineEntry,
    TimelineEntryKind,
    VideoCallReference,
)

logger = structlog.get_logger()

# Far above any real count of incidents sharing one channel id; reaching it fails closed.
_CONVERSATION_QUERY_BOUND = 10
_STORE_FAILED_MESSAGE = "The incident store is unavailable."
_RECORD_CONFLICT_MESSAGE = "The incident record was changed by another writer or is not in the shape this writer owns."
_TIMELINE_STORE_FAILED_MESSAGE = "The incident timeline store is unavailable."
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


def timeline_table(name: str) -> RecordTable:
    """Return the timeline table declaration; the keys match terraform/dynamodb.tf."""
    return RecordTable(name=name, key=KeySchema(partition=TIMELINE_PARTITION_ATTRIBUTE, sort=TIMELINE_SORT_ATTRIBUTE))


@runtime_checkable
class TimelineStore(Protocol):
    """Interface keeping an incident's timeline entries, each its own record under the incident.

    A store failure is a classified error result, never an exception.
    """

    def append(self, entry: TimelineEntry) -> OperationResult[TimelineEntry]:
        """Store ``entry`` at its key; an entry already stored at that key is a replay that writes nothing and succeeds."""
        ...


class RecordTimelineStore(TimelineStore):
    """Keep timeline entries in the timeline table through the records contract."""

    def __init__(self, records: RecordStore, table: RecordTable) -> None:
        self._records = records
        self._table = table

    def append(self, entry: TimelineEntry) -> OperationResult[TimelineEntry]:
        """Create the entry's item only where none exists."""
        result = self._records.put_if_not_exists(self._table, timeline_entry_item(entry))
        if not result.is_success:
            return _store_failure(
                result,
                operation="append",
                table=self._table,
                message=_TIMELINE_STORE_FAILED_MESSAGE,
                incident_id=entry.incident_id,
            )
        if result.data is not True:
            logger.info("incident_timeline_entry_replayed", incident_id=entry.incident_id, entry_id=entry.entry_id)
        return OperationResult.success(data=entry)


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

    Writes arrive with their slices: create, attach_conversation and set_reference with TASK-145.7;
    update_fields, set_roles and set_status with TASK-145.8; captured timeline entries with TASK-145.9.

    The field writes compute the new record from the stored one, so a change
    already stored is a replay that writes nothing. Each is one update guarded
    on the record version and on the read value of every attribute it changes;
    when another writer got there first the record is read once more and the
    change recomputed, and a second loss is PERMANENT_ERROR with
    ``INCIDENT_RECORD_CONFLICT``. A record below the current version is upgraded
    on write, in the same update, after its binding is put; one that cannot be
    upgraded is ``INCIDENT_RECORD_UNREADABLE``, and one above it is a conflict.
    """

    async def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the incident with this id."""
        ...

    async def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        """Return the one incident whose conversation is ``conversation``.

        The incident's active bindings are read first; only when none names an
        incident that exists does the lookup read the incident records' own
        conversation. The two sources are never merged. Only incidents of the
        same system and tenant count, since two tenants can share one
        conversation id. Several matches are PERMANENT_ERROR with
        ``AMBIGUOUS_INCIDENT_CONVERSATION``.
        """
        ...

    async def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return every open incident, oldest first by when it was opened."""
        ...

    async def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return whether the incident was declared as a security incident; a failure is never false."""
        ...

    async def create(self, incident: Incident) -> OperationResult[Incident]:
        """Store a new open incident's record, the commit point; no surface is attached.

        Idempotent on ``incident.id``: a retry with the same id stores the record
        once, and a replay writes nothing and returns the stored incident. Chat
        conversations are attached afterwards with ``attach_conversation``.

        Raises:
            ValueError: ``incident`` is not open or already carries a conversation.
        """
        ...

    async def attach_conversation(self, incident_id: str, binding: IncidentBinding) -> OperationResult[Incident]:
        """Bind a chat conversation to the incident and return the incident.

        A primary binding's conversation becomes the record's conversation; a
        non-primary one is another way in and leaves the record unchanged. A
        primary binding when the record names another conversation, or a record
        not of the current version, is PERMANENT_ERROR with
        ``INCIDENT_RECORD_CONFLICT`` and nothing is written. Repeating it is a no-op.

        Raises:
            ValueError: ``binding`` belongs to another incident or is archived.
        """
        ...

    async def set_reference(
        self, incident_id: str, kind: ReferenceKind, reference: ResourceReference
    ) -> OperationResult[Incident]:
        """Replace the incident's reference of ``kind`` whole and return the updated incident.

        Only an end-state record of the current version is changed; any other
        is PERMANENT_ERROR with ``INCIDENT_RECORD_CONFLICT``. Repeating it is a no-op.

        Raises:
            ValueError: ``reference`` is not the reference type of ``kind``.
        """
        ...

    async def update_fields(
        self, incident_id: str, changes: IncidentChanges, *, by: str, at: datetime
    ) -> OperationResult[Incident]:
        """Write the fields ``changes`` names and return the updated incident.

        A severity change then appends one ``severity_changed`` timeline entry by
        ``by`` at ``at``, with an id derived from the change and ``at``. A failed
        entry is retried once, then logged; it never rolls the field back.

        Raises:
            ValueError: ``by`` is blank or ``at`` is naive.
        """
        ...

    async def set_roles(self, incident_id: str, roles: Mapping[IncidentRole, str | None]) -> OperationResult[Incident]:
        """Give each named role its holder (``None`` unassigns it) and return the updated incident; other roles stay.

        Raises:
            ValueError: no role is named, a key is not an ``IncidentRole`` or a holder is blank.
        """
        ...

    async def set_status(self, incident_id: str, status: IncidentStatus, *, at: datetime) -> OperationResult[Incident]:
        """Set the status and return the updated incident.

        Closing removes the incident from the open list; reopening puts it back
        with ``at`` as its opened time; a move between open statuses changes the
        status only.

        Raises:
            ValueError: ``status`` is not an ``IncidentStatus`` or ``at`` is naive.
        """
        ...


@dataclass(frozen=True)
class _Written:
    """The incident before and after a field write; equal when the write was a replay."""

    before: Incident
    after: Incident


@dataclass(frozen=True)
class _PlannedWrite:
    current: Incident
    changes: tuple[RecordChange, ...]
    expected: dict[str, Any]
    binding: IncidentBinding | None


class _RecordIncidentStoreCalls:
    """The incident store's blocking work over the records contract; ``RecordIncidentStore`` runs each call in a thread.

    ``tenants`` is the configured tenant per workplace system, which the legacy
    item bridge gives the references of items without ``record_version``.
    ``bindings`` is the bindings table ``find_by_conversation`` reads first and
    upgrade on write puts into; ``timeline`` takes the severity entries. Neither
    has a default, so no construction can skip them.
    """

    def __init__(
        self,
        records: RecordStore,
        table: RecordTable,
        tenants: Mapping[WorkplaceSystem, str],
        *,
        bindings: RecordTable,
        timeline: TimelineStore,
    ) -> None:
        self._records = records
        self._table = table
        self._tenants = tenants
        self._bindings = bindings
        self._timeline = timeline

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

    def create(self, incident: Incident) -> OperationResult[Incident]:
        """Put the record only where none is stored; a stored record under the id is a replay, returned unchanged.

        Raises:
            ValueError: see ``IncidentStore.create``.
        """
        validate_new_incident(incident)
        stored = self._records.put_if_not_exists(self._table, incident_item(incident))
        if not stored.is_success:
            return self._failed(stored, operation="create")
        if stored.data is not True:
            logger.info("incident_create_replayed", incident_id=incident.id)
            return self.get(incident.id)
        return OperationResult.success(data=incident)

    def attach_conversation(self, incident_id: str, binding: IncidentBinding) -> OperationResult[Incident]:
        """Read the record, put the binding, then copy a primary binding's conversation into the record.

        The copy is one update guarded on ``record_version`` and on no stored
        conversation; when the guard fails the record is read once more, and the
        attach succeeds only if it now names this conversation.

        Raises:
            ValueError: see ``IncidentStore.attach_conversation``.
        """
        validate_attachment(incident_id, binding)
        operation = "attach_conversation"
        conversation = ConversationReference(
            system=binding.system, tenant=binding.tenant, vendor_id=binding.vendor_id, url=binding.url
        )
        current = self._end_state_record(incident_id, operation=operation)
        if current.data is None:
            return current
        stored = current.data
        if binding.primary and stored.conversation is not None and not _same_place(stored.conversation, conversation):
            return self._conflict(incident_id, operation=operation)
        bound = self._records.put_if_not_exists(self._bindings, binding_item(binding))
        if not bound.is_success:
            return self._failed(bound, operation=operation, table=self._bindings)
        if not binding.primary or stored.conversation is not None:
            return OperationResult.success(data=stored)
        result = self._records.update(
            self._table,
            {"id": incident_id},
            [SetAttribute("conversation", reference_item(conversation)), SetAttribute("channel_id", conversation.vendor_id)],
            expected={"record_version": RECORD_VERSION, "conversation": None},
        )
        if result.status is OperationStatus.NOT_FOUND and result.error_code is None:
            return no_such_incident()
        if not result.is_success:
            return self._failed(result, operation=operation)
        if result.data is not None:
            return self._parse(result.data, operation=operation)
        reread = self._end_state_record(incident_id, operation=operation)
        if reread.data is None:
            return reread
        if reread.data.conversation is not None and _same_place(reread.data.conversation, conversation):
            return reread
        return self._conflict(incident_id, operation=operation)

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
            return self._conflict(incident_id, operation="set_reference", kind=kind.value)
        return self._parse(result.data, operation="set_reference")

    def update_fields(self, incident_id: str, changes: IncidentChanges, *, by: str, at: datetime) -> OperationResult[Incident]:
        """Write the named fields through the guarded write, then append the severity entry when severity changed.

        Raises:
            ValueError: see ``IncidentStore.update_fields``.
        """
        validate_field_update(by, at)
        written = self._guarded_write(
            incident_id, operation="update_fields", desire=lambda current: apply_changes(current, changes)
        )
        if written.data is None:
            return _refusal(written)
        entry = severity_entry(written.data.before, written.data.after, by=by, at=at)
        if entry is not None:
            self._append_entry(entry)
        return OperationResult.success(data=written.data.after)

    def set_roles(self, incident_id: str, roles: Mapping[IncidentRole, str | None]) -> OperationResult[Incident]:
        """Write the named roles through the guarded write.

        Raises:
            ValueError: see ``IncidentStore.set_roles``.
        """
        validate_roles(roles)
        written = self._guarded_write(incident_id, operation="set_roles", desire=lambda current: apply_roles(current, roles))
        return _refusal(written) if written.data is None else OperationResult.success(data=written.data.after)

    def set_status(self, incident_id: str, status: IncidentStatus, *, at: datetime) -> OperationResult[Incident]:
        """Write the status and the open-index attributes through the guarded write.

        Raises:
            ValueError: see ``IncidentStore.set_status``.
        """
        validate_status_change(status, at)
        written = self._guarded_write(
            incident_id, operation="set_status", desire=lambda current: replace(current, status=status), at=at
        )
        return _refusal(written) if written.data is None else OperationResult.success(data=written.data.after)

    def _guarded_write(
        self, incident_id: str, *, operation: str, desire: Callable[[Incident], Incident], at: datetime | None = None
    ) -> OperationResult[_Written]:
        """Read the item, compute the change from it, then put any upgrade binding and send one guarded update.

        A lost guard reads and recomputes once; a second loss is a conflict.
        ``at`` is the reopen time when the change reopens the incident.
        """
        if not incident_id.strip():
            return no_such_incident()
        for _ in range(2):
            read = self._records.get(self._table, {"id": incident_id})
            if read.status is OperationStatus.NOT_FOUND and read.error_code is None:
                return no_such_incident()
            if not read.is_success:
                return self._failed(read, operation=operation)
            planned = self._plan_write(read.data or {}, desire, at=at, operation=operation)
            if isinstance(planned, OperationResult):
                return planned
            if not planned.changes:
                logger.info("incident_write_replayed", operation=operation, incident_id=incident_id)
                return OperationResult.success(data=_Written(planned.current, planned.current))
            if planned.binding is not None:
                bound = self._records.put_if_not_exists(self._bindings, binding_item(planned.binding))
                if not bound.is_success:
                    return self._failed(bound, operation=operation, table=self._bindings)
            result = self._records.update(self._table, {"id": incident_id}, planned.changes, expected=planned.expected)
            if result.status is OperationStatus.NOT_FOUND and result.error_code is None:
                return no_such_incident()
            if not result.is_success:
                return self._failed(result, operation=operation)
            if result.data is not None:
                parsed = self._parse(result.data, operation=operation)
                if parsed.data is None:
                    return _refusal(parsed)
                return OperationResult.success(data=_Written(planned.current, parsed.data))
            logger.info("incident_record_guard_lost", operation=operation, incident_id=incident_id)
        logger.warning("incident_record_changed", operation=operation, incident_id=incident_id)
        return record_conflict()

    def _plan_write(
        self, item: Mapping[str, Any], desire: Callable[[Incident], Incident], *, at: datetime | None, operation: str
    ) -> _PlannedWrite | OperationResult[_Written]:
        """Return the guarded update that applies ``desire`` to ``item``, upgrading it when below the current version."""
        incident_id = str(item.get("id"))
        upgrade: ItemUpgrade | None = None
        if item.get("record_version") != RECORD_VERSION:
            plan = plan_item_upgrade(item, self._tenants)
            if plan is None:
                return self._conflict(incident_id, operation=operation)
            if isinstance(plan, UnreadableLegacyItem):
                _log_unreadable(operation, plan.incident_id, plan.field, plan.value)
                return incident_record_unreadable()
            if isinstance(plan, UnboundOpenItem):
                _log_unreadable(operation, plan.incident_id, "conversation", None)
                return incident_record_unreadable()
            upgrade = plan
        current = self._parse(item, operation=operation)
        if current.data is None:
            return _refusal(current)
        changes = record_changes(current.data, desire(current.data), at=at)
        if not changes:
            return _PlannedWrite(current.data, (), {}, None)
        expected: dict[str, Any] = {"record_version": RECORD_VERSION} if upgrade is None else dict(upgrade.expected)
        try:
            for change in changes:
                expected[change.attribute] = guard_value(change.attribute, item.get(change.attribute))
        except UnguardableValueError as exc:
            _log_unreadable(operation, incident_id, exc.field, None)
            return incident_record_unreadable()
        if upgrade is None:
            return _PlannedWrite(current.data, tuple(changes), expected, None)
        # One action per attribute: the field change replaces the upgrade's Set of the same attribute.
        merged = {change.attribute: change for change in upgrade.changes} | {change.attribute: change for change in changes}
        return _PlannedWrite(current.data, tuple(merged.values()), expected, upgrade.binding)

    def _append_entry(self, entry: TimelineEntry) -> None:
        """Append ``entry``, retrying a transient failure once; a failure is logged, never raised."""
        result = self._timeline.append(entry)
        if result.status is OperationStatus.TRANSIENT_ERROR:
            result = self._timeline.append(entry)
        if not result.is_success:
            logger.warning(
                "incident_timeline_entry_failed",
                incident_id=entry.incident_id,
                entry_id=entry.entry_id,
                status=result.status.value,
                error_code=result.error_code,
            )

    def _end_state_record(self, incident_id: str, *, operation: str) -> OperationResult[Incident]:
        """Return the incident only when its stored item is an end-state record of the current version.

        A missing item is NOT_AN_INCIDENT; a legacy or other-version item is a
        conflict, since only the legacy upgrade raises it.
        """
        if not incident_id.strip():
            return no_such_incident()
        result = self._records.get(self._table, {"id": incident_id})
        if result.status is OperationStatus.NOT_FOUND and result.error_code is None:
            return no_such_incident()
        if not result.is_success:
            return self._failed(result, operation=operation)
        item: Mapping[str, Any] = result.data or {}
        if item.get("record_version") != RECORD_VERSION:
            return self._conflict(incident_id, operation=operation)
        return parse_incident_item(item)

    def _conflict[T](self, incident_id: str, *, operation: str, **fields: object) -> OperationResult[T]:
        logger.warning("incident_record_conflict", operation=operation, incident_id=incident_id, **fields)
        return record_conflict()

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
            _log_unreadable(operation, upgraded.incident_id, upgraded.field, upgraded.value)
            return None
        return upgraded.item

    def _failed[T](self, result: OperationResult[Any], *, operation: str, table: RecordTable | None = None) -> OperationResult[T]:
        return _store_failure(
            result, operation=operation, table=self._table if table is None else table, message=_STORE_FAILED_MESSAGE
        )


class RecordIncidentStore(IncidentStore):
    """Read and write incidents through the records contract, each call off the event loop.

    ``RecordStore`` is blocking, so every method runs the whole call (every
    request it makes, including a guarded write's re-read, upgrade on write and
    timeline append) in one ``asyncio.to_thread``. ``to_thread`` copies the
    context, so the structlog bindings reach the call's log lines. A running
    thread cannot be cancelled: the record client's per-attempt timeout and
    retries bound a call whose awaiting task was cancelled.

    ``tenants`` is the configured tenant per workplace system, which the legacy
    item bridge gives the references of items without ``record_version``.
    ``bindings`` is the bindings table ``find_by_conversation`` reads first and
    upgrade on write puts into; ``timeline`` takes the severity entries. Neither
    has a default, so no construction can skip them.
    """

    def __init__(
        self,
        records: RecordStore,
        table: RecordTable,
        tenants: Mapping[WorkplaceSystem, str],
        *,
        bindings: RecordTable,
        timeline: TimelineStore,
    ) -> None:
        self._calls = _RecordIncidentStoreCalls(records, table, tenants, bindings=bindings, timeline=timeline)

    async def get(self, incident_id: str) -> OperationResult[Incident]:
        """Return the incident with this id."""
        return await asyncio.to_thread(self._calls.get, incident_id)

    async def find_by_conversation(self, conversation: ConversationReference) -> OperationResult[Incident]:
        """Return the one incident whose conversation is ``conversation``: bindings first, then the records."""
        return await asyncio.to_thread(self._calls.find_by_conversation, conversation)

    async def list_open(self) -> OperationResult[Sequence[Incident]]:
        """Return every open incident, oldest first by when it was opened."""
        return await asyncio.to_thread(self._calls.list_open)

    async def read_security_flag(self, incident_id: str) -> OperationResult[bool]:
        """Return whether the incident was declared as a security incident; a failure is never false."""
        return await asyncio.to_thread(self._calls.read_security_flag, incident_id)

    async def create(self, incident: Incident) -> OperationResult[Incident]:
        """Write the end-state record alone; idempotent on the incident id."""
        return await asyncio.to_thread(self._calls.create, incident)

    async def attach_conversation(self, incident_id: str, binding: IncidentBinding) -> OperationResult[Incident]:
        """Bind a chat conversation to the incident."""
        return await asyncio.to_thread(self._calls.attach_conversation, incident_id, binding)

    async def set_reference(
        self, incident_id: str, kind: ReferenceKind, reference: ResourceReference
    ) -> OperationResult[Incident]:
        """Set one of the incident's resource references."""
        return await asyncio.to_thread(self._calls.set_reference, incident_id, kind, reference)

    async def update_fields(
        self, incident_id: str, changes: IncidentChanges, *, by: str, at: datetime
    ) -> OperationResult[Incident]:
        """Apply a field update, guarded on ``record_version`` and the read values it changes."""
        return await asyncio.to_thread(self._calls.update_fields, incident_id, changes, by=by, at=at)

    async def set_roles(self, incident_id: str, roles: Mapping[IncidentRole, str | None]) -> OperationResult[Incident]:
        """Give each named role its holder (``None`` unassigns it); other roles stay."""
        return await asyncio.to_thread(self._calls.set_roles, incident_id, roles)

    async def set_status(self, incident_id: str, status: IncidentStatus, *, at: datetime) -> OperationResult[Incident]:
        """Set the incident's status; closing and reopening move it out of and into the open index."""
        return await asyncio.to_thread(self._calls.set_status, incident_id, status, at=at)


def _log_unreadable(operation: str, incident_id: object, field: str, value: object) -> None:
    """Log an item the store cannot read; the value only for status, since other legacy values may be vendor links."""
    log_fields: dict[str, object] = {"operation": operation, "incident_id": incident_id, "field": field}
    if field == "status":
        log_fields["value"] = value
    logger.warning("incident_record_unreadable", **log_fields)


def _store_failure[T](
    result: OperationResult[Any], *, operation: str, table: RecordTable, message: str, **context: object
) -> OperationResult[T]:
    """Classify a backend failure: its status, code and retry hint, with a generic message."""
    status = result.status
    if status is OperationStatus.NOT_FOUND:
        # A missing table or index is a broken store; NOT_FOUND is reserved for "not an incident".
        status = OperationStatus.PERMANENT_ERROR
    logger.warning(
        "incident_store_failed",
        operation=operation,
        table=table.name,
        status=status.value,
        error_code=result.error_code,
        **context,
    )
    return OperationResult.error(status, message=message, error_code=result.error_code, retry_after=result.retry_after)


def apply_changes(current: Incident, changes: IncidentChanges) -> Incident:
    """Return ``current`` with the fields ``changes`` names; shared by the real store and the fake."""
    return replace(current, **changes.named())


def apply_roles(current: Incident, roles: Mapping[IncidentRole, str | None]) -> Incident:
    """Return ``current`` with each named role given its holder; shared by the real store and the fake."""
    holders: dict[str, Any] = {role.value: holder for role, holder in roles.items()}
    return replace(current, **holders)


def record_changes(current: Incident, desired: Incident, *, at: datetime | None) -> list[RecordChange]:
    """Return the attribute changes that turn the stored ``current`` into ``desired``; none when they are equal.

    A field set to ``None`` is removed. Closing removes ``open_bucket`` and
    ``opened_at``; reopening sets them, ``opened_at`` being ``at``.
    """
    stored = incident_item(desired)
    changes: list[RecordChange] = []
    for field in fields(Incident):
        if getattr(current, field.name) != getattr(desired, field.name):
            changes.append(SetAttribute(field.name, stored[field.name]) if field.name in stored else RemoveAttribute(field.name))
    if current.status.is_open and not desired.status.is_open:
        changes += [RemoveAttribute("open_bucket"), RemoveAttribute("opened_at")]
    elif desired.status.is_open and not current.status.is_open:
        if at is None:
            raise ValueError("reopening an incident needs the time it reopened")
        changes += [SetAttribute("open_bucket", OPEN_BUCKET), SetAttribute("opened_at", format_stored_time(at))]
    return changes


def severity_entry(before: Incident, after: Incident, *, by: str, at: datetime) -> TimelineEntry | None:
    """Return the severity_changed entry for a write from ``before`` to ``after``; ``None`` when severity did not change."""
    if before.severity == after.severity:
        return None
    change = SeverityChange(previous=before.severity, current=after.severity)
    return TimelineEntry(
        incident_id=after.id,
        entry_id=severity_entry_id(after.id, change, at),
        posted_at=at,
        author=by,
        text="",
        kind=TimelineEntryKind.SEVERITY_CHANGED,
        severity_change=change,
    )


def validate_field_update(by: str, at: datetime) -> None:
    """Refuse a field update without its author or with a naive time; shared by the real store and the fake.

    Raises:
        ValueError: ``by`` is blank or ``at`` is naive.
    """
    if not by.strip():
        raise ValueError("by must name who made the change")
    _require_aware_time(at)


def validate_roles(roles: Mapping[IncidentRole, str | None]) -> None:
    """Refuse roles the record cannot hold; shared by the real store and the fake.

    Raises:
        ValueError: no role is named, a key is not an ``IncidentRole`` or a holder is blank.
    """
    if not roles:
        raise ValueError("a role update names at least one role")
    for role, holder in roles.items():
        if not isinstance(role, IncidentRole):
            raise ValueError(f"each role must be an IncidentRole member, got {role!r}")
        if holder is not None and not holder.strip():
            raise ValueError(f"{role.value} must name a holder or be None")


def validate_status_change(status: IncidentStatus, at: datetime) -> None:
    """Refuse a status the record cannot hold or a naive time; shared by the real store and the fake.

    Raises:
        ValueError: ``status`` is not an ``IncidentStatus`` member or ``at`` is naive.
    """
    if not isinstance(status, IncidentStatus):
        raise ValueError(f"status must be an IncidentStatus member, got {status!r}")
    _require_aware_time(at)


def _require_aware_time(at: datetime) -> None:
    if at.utcoffset() is None:
        raise ValueError("at must be timezone-aware")


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


def validate_new_incident(incident: Incident) -> None:
    """Refuse a create the record could not honour; shared by the real store and the fake.

    Raises:
        ValueError: ``incident`` is not open, or already carries a conversation,
            which arrives only through ``attach_conversation`` so the record's copy
            and the binding cannot disagree.
    """
    if incident.status is not IncidentStatus.OPEN:
        raise ValueError(f"a created incident must be open, got {incident.status}")
    if incident.conversation is not None:
        raise ValueError("a created incident has no conversation yet: attach it with attach_conversation")


def validate_attachment(incident_id: str, binding: IncidentBinding) -> None:
    """Refuse a binding that cannot be attached to ``incident_id``; shared by the real store and the fake.

    Raises:
        ValueError: ``binding`` belongs to another incident, is not a chat
            conversation, or is archived.
    """
    if binding.incident_id != incident_id:
        raise ValueError("binding.incident_id must be the incident it is attached to")
    if binding.kind is not BindingKind.CHAT_CONVERSATION:
        raise ValueError(f"only a chat conversation is attached, got {binding.kind}")
    if binding.archived_at is not None:
        raise ValueError("an archived binding cannot be attached")


def _same_place(stored: ConversationReference, conversation: ConversationReference) -> bool:
    """Whether two conversation references name the same conversation; the url is a hint and not compared."""
    return (stored.system, stored.tenant, stored.vendor_id) == (conversation.system, conversation.tenant, conversation.vendor_id)


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

    async def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence.

        The caller numbers it: the latest update's sequence plus one, or 1.
        Any record already at that sequence is a conflict.
        """
        ...

    async def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update in one read; success with ``None`` when it has none."""
        ...

    async def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        """Return every update of the incident, newest first."""
        ...

    async def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        """Replace the stored update with ``update`` while its stored state is ``expected_state``.

        Used to approve (with the approver and edited text), to publish (with
        the time and the person) and to unpublish (clearing both). A stored
        state that moved on, or no stored record, is a conflict.

        Raises:
            ValueError: ``expected_state`` cannot move to ``update.state``.
        """
        ...


class _RecordStatusUpdateStoreCalls:
    """The status-update store's blocking work over the records contract; ``RecordStatusUpdateStore`` runs each call in a thread."""

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


class RecordStatusUpdateStore(StatusUpdateStore):
    """Keep status updates in the status-updates table through the records contract, each call off the event loop.

    Every method runs the whole call in one ``asyncio.to_thread``, as
    ``RecordIncidentStore`` does.
    """

    def __init__(self, records: RecordStore, table: RecordTable) -> None:
        self._calls = _RecordStatusUpdateStoreCalls(records, table)

    async def append(self, update: StatusUpdate) -> OperationResult[StatusUpdate]:
        """Store a new update at its sequence."""
        return await asyncio.to_thread(self._calls.append, update)

    async def latest(self, incident_id: str) -> OperationResult[StatusUpdate | None]:
        """Return the incident's highest-sequence update, or ``None``."""
        return await asyncio.to_thread(self._calls.latest, incident_id)

    async def list_for_incident(self, incident_id: str) -> OperationResult[Sequence[StatusUpdate]]:
        """Return every update of the incident, newest first."""
        return await asyncio.to_thread(self._calls.list_for_incident, incident_id)

    async def transition(self, update: StatusUpdate, *, expected_state: StatusUpdateState) -> OperationResult[StatusUpdate]:
        """Replace the stored update with ``update`` while its stored state is ``expected_state``."""
        return await asyncio.to_thread(self._calls.transition, update, expected_state=expected_state)
