"""The webhooks stores on the records contract: instances and the durable inbox.

Both are async ports over the sync ``RecordStore``; each call runs its record work in one
``asyncio.to_thread`` inside the adapter, never in its callers (decisions/outbound-clients.md
async ports). Stored items are untrusted on read (decisions/managed-content.md): an instance
missing a required attribute is unreadable and logged, never guessed (cloud-portability.md
persisted enum values). No raw attribute shape leaves this module (decisions/webhooks.md Checks).

The inbox item's own conditional insert is the delivery dedupe, and every later write is a
guarded update on the state and owner the writer read. A guarded update the SDK retried after
a lost response reports its guard unmet; the store settles it with one strongly consistent
read before reporting the guard lost (decisions/outbound-clients.md, unconfirmed writes).
"""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from capabilities.webhooks.domain.inbox import DUE_STATES, InboxItem, ItemKind, ItemState
from capabilities.webhooks.domain.kinds import AuthTier, Destination, InstanceState, Owner, WebhookInstance
from capabilities.webhooks.interfaces import InboxStore, WebhookStore
from contracts.operations import OperationResult, OperationStatus
from contracts.records import (
    KeySchema,
    RecordIndex,
    RecordQuery,
    RecordStore,
    RecordTable,
    RemoveAttribute,
    SetAttribute,
    SortCondition,
    SortOperator,
)
from contracts.workplace import WorkplaceSystem

logger = structlog.get_logger()

# Attribute names; the indexes match terraform/dynamodb.tf.
INSTANCE_REF = "instance_ref"
DUE_BUCKET = "due"
DUE_BUCKET_VALUE = "due"
DUE_AT = "due_at"
RECEIVED_AT = "received_at"
_INBOX_KEY = "item_key"
_MUTABLE = ("state", "owner", DUE_BUCKET, DUE_AT, "attempts", "done_targets", "last_error")
_UNREADABLE = "a stored webhook item could not be read"


def instances_table(name: str) -> RecordTable:
    """The instances table: keyed by the URL token, with a sparse index on ``instance_ref``."""
    return RecordTable(
        name=name,
        key=KeySchema(partition="id"),
        indexes={"by_instance_ref": RecordIndex(physical_name="by_instance_ref", key=KeySchema(partition=INSTANCE_REF))},
    )


def inbox_table(name: str) -> RecordTable:
    """The inbox table: sparse indexes for due items (the sweeper) and per-instance history."""
    return RecordTable(
        name=name,
        key=KeySchema(partition=_INBOX_KEY),
        indexes={
            "by_due": RecordIndex(physical_name="by_due", key=KeySchema(partition=DUE_BUCKET, sort=DUE_AT)),
            "by_instance": RecordIndex(physical_name="by_instance", key=KeySchema(partition=INSTANCE_REF, sort=RECEIVED_AT)),
        },
    )


def _number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | Decimal):
        raise ValueError("not a number")
    return int(value)


def _strings(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple) or not all(isinstance(entry, str) for entry in value):
        raise ValueError("not a list of strings")
    return tuple(value)


def _text(item: Mapping[str, Any], name: str) -> str:
    value = item.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is missing")
    return value


def _destination(raw: object) -> Destination | None:
    if not isinstance(raw, Mapping):
        return None
    try:
        return Destination(
            system=WorkplaceSystem(_text(raw, "system")),
            tenant=str(raw.get("tenant", "")),
            conversation_id=str(raw.get("conversation_id", "")),
            triage=raw.get("triage") is True,
        )
    except ValueError:
        return None


def instance_from_item(item: Mapping[str, Any]) -> WebhookInstance | None:
    """The instance a stored item describes; None for a legacy-only item (not provisioned).

    Raises:
        ValueError: A provisioned item misses a required attribute or holds an unknown value.
    """
    if not item.get(INSTANCE_REF) or not item.get("protocol"):
        return None
    owner = item.get("owner")
    if not isinstance(owner, Mapping):
        raise ValueError("owner is missing")
    destinations = []
    for raw in item.get("destinations") or ():
        destination = _destination(raw)
        if destination is None:
            logger.warning("webhook_destination_unreadable", instance_ref=item[INSTANCE_REF])
            continue
        destinations.append(destination)
    stored_state = item.get("state")
    if stored_state is None:
        state = InstanceState.ACTIVE if item.get("active", True) is True else InstanceState.DISABLED
    else:
        state = InstanceState(stored_state)
    return WebhookInstance(
        instance_ref=_text(item, INSTANCE_REF),
        name=_text(item, "name"),
        owner=Owner(team=_text(owner, "team"), contact=_text(owner, "contact")),
        auth_tier=AuthTier(_text(item, "auth_tier")),
        protocol=_text(item, "protocol"),
        sender_kinds=_strings(item.get("sender_kinds")),
        destinations=tuple(destinations),
        state=state,
        topic_arns=_strings(item.get("topic_arns")),
    )


def _failed[T](result: OperationResult[Any], operation: str) -> OperationResult[T]:
    logger.warning("webhook_store_failed", operation=operation, status=result.status.value, error_code=result.error_code)
    return OperationResult.error(
        status=result.status,
        message="the webhook store is unavailable",
        error_code=result.error_code,
        retry_after=result.retry_after,
    )


class RecordWebhookStore(WebhookStore):
    """Instances in the webhooks table."""

    def __init__(self, records: RecordStore, table: RecordTable) -> None:
        self._records = records
        self._table = table

    async def by_url_id(self, webhook_id: str) -> OperationResult[WebhookInstance]:
        """The provisioned instance behind a URL token."""
        return await asyncio.to_thread(self._by_url_id, webhook_id)

    async def by_ref(self, instance_ref: str) -> OperationResult[WebhookInstance]:
        """The provisioned instance with ``instance_ref``."""
        return await asyncio.to_thread(self._by_ref, instance_ref)

    def _by_url_id(self, webhook_id: str) -> OperationResult[WebhookInstance]:
        result = self._records.get(self._table, {"id": webhook_id})
        if result.status is OperationStatus.NOT_FOUND and result.error_code is None:
            return OperationResult.error(OperationStatus.NOT_FOUND, "no such instance")
        if not result.is_success:
            return _failed(result, "instance_by_url_id")
        return self._read(result.data)

    def _by_ref(self, instance_ref: str) -> OperationResult[WebhookInstance]:
        result = self._records.query(self._table, RecordQuery(partition=instance_ref, index="by_instance_ref", limit=2))
        if not result.is_success:
            return _failed(result, "instance_by_ref")
        items = list(result.data or [])
        if len(items) != 1:
            if items:
                logger.warning("webhook_instance_ref_ambiguous", instance_ref=instance_ref, count=len(items))
            return OperationResult.error(OperationStatus.NOT_FOUND, "no such instance")
        return self._read(items[0])

    @staticmethod
    def _read(item: object) -> OperationResult[WebhookInstance]:
        if not isinstance(item, Mapping):
            return OperationResult.error(OperationStatus.NOT_FOUND, "no such instance")
        try:
            instance = instance_from_item(item)
        except ValueError as exc:
            logger.warning("webhook_instance_unreadable", instance_ref=item.get(INSTANCE_REF), reason=str(exc))
            return OperationResult.error(OperationStatus.NOT_FOUND, "no such instance")
        if instance is None:
            return OperationResult.error(OperationStatus.NOT_FOUND, "no such instance")
        return OperationResult.success(data=instance)


def _mutable_attributes(item: InboxItem) -> dict[str, Any]:
    attributes: dict[str, Any] = {
        "state": item.state.value,
        "owner": item.owner,
        "attempts": item.attempts,
        "done_targets": sorted(item.done_targets),
        "last_error": item.last_error,
        DUE_BUCKET: DUE_BUCKET_VALUE if item.state in DUE_STATES and item.due_at is not None else None,
        DUE_AT: item.due_at if item.state in DUE_STATES else None,
    }
    return attributes


def inbox_record(item: InboxItem) -> dict[str, Any]:
    """The stored shape of ``item``; absent attributes are left out, so the due index stays sparse."""
    record: dict[str, Any] = {
        _INBOX_KEY: item.key,
        INSTANCE_REF: item.instance_ref,
        "delivery_id": item.delivery_id,
        "protocol": item.protocol,
        "kind": item.kind.value,
        "envelope": json.dumps(item.envelope, ensure_ascii=False, separators=(",", ":")),
        RECEIVED_AT: int(item.received_at.timestamp() * 1000),
        "expires_at": item.expires_at,
        "fingerprint": list(item.fingerprint),
        "subscribe_url": item.subscribe_url,
        **_mutable_attributes(item),
    }
    return {name: value for name, value in record.items() if value is not None}


def inbox_item(record: Mapping[str, Any]) -> InboxItem:
    """The item a stored record holds.

    Raises:
        ValueError: The record misses an attribute or holds an unknown value.
    """
    envelope = json.loads(_text(record, "envelope"))
    due_at = record.get(DUE_AT)
    owner = record.get("owner")
    return InboxItem(
        key=_text(record, _INBOX_KEY),
        instance_ref=_text(record, INSTANCE_REF),
        delivery_id=_text(record, "delivery_id"),
        protocol=_text(record, "protocol"),
        kind=ItemKind(_text(record, "kind")),
        envelope=envelope,
        received_at=datetime.fromtimestamp(_number(record.get(RECEIVED_AT)) / 1000, tz=UTC),
        expires_at=_number(record.get("expires_at")),
        state=ItemState(_text(record, "state")),
        owner=owner if isinstance(owner, str) else None,
        due_at=None if due_at is None else _number(due_at),
        attempts=_number(record.get("attempts")),
        done_targets=frozenset(_strings(record.get("done_targets"))),
        fingerprint=_strings(record.get("fingerprint")),
        subscribe_url=record.get("subscribe_url") if isinstance(record.get("subscribe_url"), str) else None,
        last_error=record.get("last_error") if isinstance(record.get("last_error"), str) else None,
    )


class RecordInboxStore(InboxStore):
    """The inbox in its own records table."""

    def __init__(self, records: RecordStore, table: RecordTable) -> None:
        self._records = records
        self._table = table

    async def insert(self, item: InboxItem) -> OperationResult[bool]:
        """Insert ``item`` only where its key is free."""
        return await asyncio.to_thread(self._insert, item)

    async def get(self, key: str) -> OperationResult[InboxItem]:
        """Read one item."""
        return await asyncio.to_thread(self._get, key)

    async def replace(self, current: InboxItem, new: InboxItem) -> OperationResult[InboxItem]:
        """Write ``new``'s changes, guarded on ``current``'s state and owner."""
        return await asyncio.to_thread(self._replace, current, new)

    async def due(self, now: datetime, limit: int) -> OperationResult[tuple[InboxItem, ...]]:
        """The due items, oldest first."""
        return await asyncio.to_thread(self._due, now, limit)

    def _insert(self, item: InboxItem) -> OperationResult[bool]:
        result = self._records.put_if_not_exists(self._table, inbox_record(item))
        if not result.is_success or not isinstance(result.data, bool):
            return _failed(result, "inbox_insert")
        return OperationResult.success(data=result.data)

    def _get(self, key: str) -> OperationResult[InboxItem]:
        result = self._records.get(self._table, {_INBOX_KEY: key})
        if result.status is OperationStatus.NOT_FOUND and result.error_code is None:
            return OperationResult.error(OperationStatus.NOT_FOUND, "no such item")
        if not result.is_success:
            return _failed(result, "inbox_get")
        if not isinstance(result.data, Mapping):
            return OperationResult.permanent_error(_UNREADABLE)
        try:
            return OperationResult.success(data=inbox_item(result.data))
        except (ValueError, TypeError) as exc:
            logger.warning("webhook_inbox_item_unreadable", reason=str(exc))
            return OperationResult.permanent_error(_UNREADABLE)

    def _replace(self, current: InboxItem, new: InboxItem) -> OperationResult[InboxItem]:
        if new.key != current.key:
            raise ValueError("an item's key never changes")
        wanted = _mutable_attributes(new)
        changes = [SetAttribute(name, wanted[name]) if wanted[name] is not None else RemoveAttribute(name) for name in _MUTABLE]
        result = self._records.update(
            self._table,
            {_INBOX_KEY: current.key},
            changes,
            expected={"state": current.state.value, "owner": current.owner},
        )
        if result.is_success and result.data is not None:
            return OperationResult.success(data=new)
        if not result.is_success and not (result.status is OperationStatus.NOT_FOUND and result.error_code is None):
            return _failed(result, "inbox_replace")
        # The guard was unmet: either another worker owns the item, or the SDK retried our own write.
        stored = self._get(current.key)
        if stored.is_success and stored.data is not None and _mutable_attributes(stored.data) == wanted:
            return OperationResult.success(data=new)
        return OperationResult.success(data=None, message="guard lost")

    def _due(self, now: datetime, limit: int) -> OperationResult[tuple[InboxItem, ...]]:
        query = RecordQuery(
            partition=DUE_BUCKET_VALUE,
            index="by_due",
            sort=SortCondition(SortOperator.LT, int(now.timestamp()) + 1),
            limit=limit,
        )
        result = self._records.query(self._table, query)
        if not result.is_success:
            return _failed(result, "inbox_due")
        items: list[InboxItem] = []
        for record in result.data or ():
            try:
                items.append(inbox_item(record))
            except (ValueError, TypeError) as exc:
                logger.warning("webhook_inbox_item_unreadable", reason=str(exc))
        return OperationResult.success(data=tuple(items))
