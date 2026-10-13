"""Unit tests for behaviour specific to the in-memory record store.

Shared query and write semantics are covered against both stores by the
integration conformance suite; these cases pin what only the fake decides:
missing key attributes, copy isolation and sparse-index exclusion.
"""

import pytest

from contracts.operations.status import OperationStatus
from infrastructure.records.in_memory import InMemoryRecordStore
from infrastructure.records.protocol import KeySchema, RecordIndex, RecordQuery, RecordTable

pytestmark = pytest.mark.unit

TABLE = RecordTable(
    name="events",
    key=KeySchema(partition="PK", sort="SK"),
    indexes={"by_user": RecordIndex(physical_name="user-index", key=KeySchema(partition="user", sort="ts"))},
)


@pytest.mark.parametrize("item", [{"SK": "1"}, {"PK": "a"}])
def test_put_without_full_key_is_a_permanent_error(item: dict[str, str]) -> None:
    store = InMemoryRecordStore()

    result = store.put(TABLE, item)

    assert result.status == OperationStatus.PERMANENT_ERROR


def test_put_if_not_exists_without_full_key_is_a_permanent_error() -> None:
    store = InMemoryRecordStore()

    result = store.put_if_not_exists(TABLE, {"PK": "a"})

    assert result.status == OperationStatus.PERMANENT_ERROR


def test_stored_items_are_isolated_from_caller_mutation() -> None:
    store = InMemoryRecordStore()
    item = {"PK": "a", "SK": "1", "tags": ["x"]}
    store.put(TABLE, item)

    item["tags"].append("y")
    fetched = store.get(TABLE, {"PK": "a", "SK": "1"}).data
    fetched["tags"].append("z")

    assert store.get(TABLE, {"PK": "a", "SK": "1"}).data["tags"] == ["x"]


def test_index_query_excludes_items_missing_the_index_sort_attribute() -> None:
    store = InMemoryRecordStore()
    store.put(TABLE, {"PK": "a", "SK": "1", "user": "alice", "ts": "1"})
    store.put(TABLE, {"PK": "b", "SK": "1", "user": "alice"})

    result = store.query(TABLE, RecordQuery(partition="alice", index="by_user"))

    assert [item["PK"] for item in result.data] == ["a"]


def test_tables_are_isolated_by_name() -> None:
    store = InMemoryRecordStore()
    other = RecordTable(name="other", key=TABLE.key)
    store.put(TABLE, {"PK": "a", "SK": "1"})

    assert store.get(other, {"PK": "a", "SK": "1"}).status == OperationStatus.NOT_FOUND
