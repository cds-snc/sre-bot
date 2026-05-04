"""Unit tests for the in-memory fake storage implementation."""

from __future__ import annotations

import pytest

from tests.unit.infrastructure.storage.fake_storage import FakeStorageService


@pytest.mark.unit
def test_fake_storage_put_and_get() -> None:
    storage = FakeStorageService()

    put_result = storage.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})
    get_result = storage.get("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})

    assert put_result.is_success
    assert get_result.is_success
    assert get_result.data == {"PK": "RESOURCE#1", "SK": "EVENT#1"}


@pytest.mark.unit
def test_fake_storage_query() -> None:
    storage = FakeStorageService()
    storage.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})
    storage.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#2"})
    storage.put("audit", {"PK": "RESOURCE#2", "SK": "EVENT#1"})

    result = storage.query(
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
def test_fake_storage_delete() -> None:
    storage = FakeStorageService()
    storage.put("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})

    delete_result = storage.delete("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})
    get_result = storage.get("audit", {"PK": "RESOURCE#1", "SK": "EVENT#1"})

    assert delete_result.is_success
    assert not get_result.is_success
