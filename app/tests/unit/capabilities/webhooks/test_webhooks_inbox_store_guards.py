"""Unit tests for the inbox store on the records contract.

The store runs over ``InMemoryRecordStore``, the records contract's conformance-tested fake, so
the conditional insert and guarded updates behave as the DynamoDB store's do. A failing record
store is a small stub returning a transient error. Assertions read the store back, so each test
proves what was persisted, not what a method returned.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from capabilities.webhooks.domain.inbox import (
    InboxItem,
    ItemKind,
    ItemState,
    ProtocolDelivery,
    claimed,
    finished,
    new_item,
    retry_scheduled,
    with_target_done,
)
from capabilities.webhooks.store import RecordInboxStore, inbox_record, inbox_table
from contracts.operations import OperationResult, OperationStatus
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)
TABLE = inbox_table("inbox")


def _item(delivery_id: str = "m-1", owner: str = "token-a") -> InboxItem:
    delivery = ProtocolDelivery(delivery_id=delivery_id, kind=ItemKind.EVENT, document={"Message": {"a": 1}})
    return new_item("ref-1", "aws_sns", delivery, now=NOW, owner=owner, lease_seconds=35, ttl_seconds=604800)


@pytest.fixture
def records() -> InMemoryRecordStore:
    return InMemoryRecordStore()


@pytest.fixture
def store(records: InMemoryRecordStore) -> RecordInboxStore:
    return RecordInboxStore(records, TABLE)


async def test_the_first_insert_is_new_and_a_redelivery_is_a_duplicate(store: RecordInboxStore) -> None:
    first = await store.insert(_item())
    second = await store.insert(_item(owner="token-b"))

    assert (first.data, second.data) == (True, False)
    stored = await store.get(_item().key)
    assert stored.data is not None and stored.data.owner == "token-a"


async def test_an_item_round_trips_through_its_stored_shape(store: RecordInboxStore) -> None:
    item = with_target_done(_item(), "post:slack:T1:C1")
    await store.insert(item)

    stored = await store.get(item.key)

    assert stored.data == item


class _UnavailableRecords(InMemoryRecordStore):
    def put_if_not_exists(self, table: Any, item: dict[str, Any]) -> OperationResult:
        return OperationResult.transient_error("throttled")


async def test_an_insert_the_store_cannot_confirm_is_a_failure_never_a_duplicate() -> None:
    """Fail closed: anything but a confirmed insert is reported as a failure, so the route answers 503."""
    result = await RecordInboxStore(_UnavailableRecords(), TABLE).insert(_item())

    assert result.status is OperationStatus.TRANSIENT_ERROR


async def test_a_transition_applies_only_under_the_state_and_owner_read(store: RecordInboxStore) -> None:
    item = _item()
    await store.insert(item)
    done = finished(item, ItemState.DONE)

    applied = await store.replace(item, done)
    stale = await store.replace(item, retry_scheduled(item, retry_at=1, error="late"))

    assert applied.data == done
    assert stale.is_success and stale.data is None
    stored = await store.get(item.key)
    assert stored.data is not None and stored.data.state is ItemState.DONE


async def test_a_takeover_locks_out_the_previous_owner(store: RecordInboxStore) -> None:
    """After the sweeper takes an expired lease, the inline worker's late write changes nothing."""
    item = _item()
    await store.insert(item)
    taken = claimed(item, owner="token-b", now=NOW + timedelta(minutes=5), lease_seconds=35)
    assert (await store.replace(item, taken)).data == taken

    late = await store.replace(item, finished(item, ItemState.DONE))

    assert late.data is None
    stored = await store.get(item.key)
    assert stored.data is not None and (stored.data.owner, stored.data.attempts) == ("token-b", 2)


async def test_a_replayed_write_that_already_landed_counts_as_applied(
    store: RecordInboxStore, records: InMemoryRecordStore
) -> None:
    """The SDK retried an update whose first attempt landed: the store reads back its own write."""
    item = _item()
    await store.insert(item)
    done = finished(item, ItemState.DONE)
    await store.replace(item, done)

    replayed = await store.replace(item, done)

    assert replayed.data == done


async def test_only_due_items_are_in_the_due_index(store: RecordInboxStore, records: InMemoryRecordStore) -> None:
    leased = _item("m-1")
    retrying = retry_scheduled(_item("m-2"), retry_at=int(NOW.timestamp()) - 1, error="x")
    later = retry_scheduled(_item("m-3"), retry_at=int(NOW.timestamp()) + 600, error="x")
    terminal = finished(_item("m-4"), ItemState.DEAD)
    for item in (leased, retrying, later, terminal):
        await store.insert(item)

    due = await store.due(NOW + timedelta(seconds=60), limit=10)

    assert due.data is not None
    assert {item.delivery_id for item in due.data} == {"m-1", "m-2"}
    assert "due" not in inbox_record(terminal) and "due_at" not in inbox_record(terminal)
