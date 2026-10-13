"""Unit tests for the in-memory record store fake."""

import pytest

from tests.unit.infrastructure.records.in_memory_record_store import InMemoryRecordStore


@pytest.mark.unit
def test_in_memory_record_store_put_and_get() -> None:
    store = InMemoryRecordStore()

    put_result = store.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})
    get_result = store.get("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})

    assert put_result.is_success
    assert get_result.is_success
    assert get_result.data == {"PK": "RESOURCE#1", "SK": "EVENT#1"}


@pytest.mark.unit
def test_in_memory_record_store_query() -> None:
    store = InMemoryRecordStore()
    store.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})
    store.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#2"})
    store.put("audit", {"PK": "RESOURCE#2", "SK": "EVENT#1"})

    result = store.query(
        "audit",
        key_condition="PK = :pk",
        expression_values={":pk": "RESOURCE#1"},
        ScanIndexForward=False,
    )

    assert result.is_success
    assert result.data == [
        {"PK": "RESOURCE#1", "SK": "EVENT#2"},
        {"PK": "RESOURCE#1", "SK": "EVENT#1"},
    ]


@pytest.mark.unit
def test_in_memory_record_store_delete() -> None:
    store = InMemoryRecordStore()
    store.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})

    delete_result = store.delete("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})
    get_result = store.get("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})

    assert delete_result.is_success
    assert not get_result.is_success
