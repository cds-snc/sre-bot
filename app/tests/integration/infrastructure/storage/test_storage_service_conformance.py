"""Moto-backed conformance suite for DynamoDBStorageService.

Exercises real DynamoDB ConditionExpression and paginator semantics that
MagicMock-based unit tests cannot verify.
"""

from decimal import Decimal

import pytest

from infrastructure.operations.status import OperationStatus
from infrastructure.storage.service import DynamoDBStorageService

from .conftest import STORAGE_TEST_TABLE_NAME

TABLE = STORAGE_TEST_TABLE_NAME

pytestmark = pytest.mark.integration


class TestPutAndGet:
    """put/get roundtrip including numeric and boolean field serialization."""

    def test_put_get_roundtrip(self, storage_service: DynamoDBStorageService) -> None:
        item = {"pk": "test-pk-1", "sk": "2026-01-01", "count": 42, "active": True}
        put_result = storage_service.put(TABLE, item)
        assert put_result.is_success

        get_result = storage_service.get(TABLE, {"pk": "test-pk-1", "sk": "2026-01-01"})
        assert get_result.is_success
        data = get_result.data
        assert data is not None
        assert data["pk"] == "test-pk-1"
        assert data["sk"] == "2026-01-01"
        assert data["count"] == Decimal("42")
        assert data["active"] is True

    def test_get_missing_key_returns_not_found(self, storage_service: DynamoDBStorageService) -> None:
        result = storage_service.get(TABLE, {"pk": "nonexistent", "sk": "nonexistent"})
        assert not result.is_success
        assert result.status == OperationStatus.NOT_FOUND


class TestPutIfNotExists:
    """real attribute_not_exists ConditionExpression rejects duplicates."""

    def test_first_call_creates_item(self, storage_service: DynamoDBStorageService) -> None:
        item = {"pk": "unique-pk", "sk": "sk-1", "value": "hello"}
        result = storage_service.put_if_not_exists(TABLE, item, pk_attribute="pk")
        assert result.is_success
        assert result.data is True

    def test_second_call_with_same_key_is_rejected(self, storage_service: DynamoDBStorageService) -> None:
        # attribute_not_exists(pk) guards the exact (pk, sk) coordinate in a composite-key table.
        item = {"pk": "duplicate-pk", "sk": "sk-1", "value": "first"}
        storage_service.put_if_not_exists(TABLE, item, pk_attribute="pk")

        duplicate = {"pk": "duplicate-pk", "sk": "sk-1", "value": "second"}
        result = storage_service.put_if_not_exists(TABLE, duplicate, pk_attribute="pk")
        assert result.is_success
        assert result.data is False


class TestDelete:
    """delete removes the item; subsequent get returns NOT_FOUND."""

    def test_delete_removes_item(self, storage_service: DynamoDBStorageService) -> None:
        item = {"pk": "delete-pk", "sk": "sk-1", "value": "to-be-deleted"}
        storage_service.put(TABLE, item)

        delete_result = storage_service.delete(TABLE, {"pk": "delete-pk", "sk": "sk-1"})
        assert delete_result.is_success

        get_result = storage_service.get(TABLE, {"pk": "delete-pk", "sk": "sk-1"})
        assert get_result.status == OperationStatus.NOT_FOUND


class TestQuery:
    """pagination via get_paginator aggregates items across page boundaries."""

    def _put_items(self, storage_service: DynamoDBStorageService) -> None:
        for i in range(1, 4):
            storage_service.put(TABLE, {"pk": "query-pk", "sk": f"sk-{i}", "idx": i})

    def test_query_returns_all_items(self, storage_service: DynamoDBStorageService) -> None:
        self._put_items(storage_service)
        result = storage_service.query(
            TABLE,
            key_condition="pk = :pk",
            expression_values={":pk": "query-pk"},
        )
        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 3
        sk_values = {item["sk"] for item in result.data}
        assert sk_values == {"sk-1", "sk-2", "sk-3"}

    def test_query_with_limit_forces_pagination(self, storage_service: DynamoDBStorageService) -> None:
        self._put_items(storage_service)
        # Limit=1 forces the paginator to walk multiple pages; all items must still be returned.
        result = storage_service.query(
            TABLE,
            key_condition="pk = :pk",
            expression_values={":pk": "query-pk"},
            Limit=1,
        )
        assert result.is_success
        assert result.data is not None
        assert len(result.data) == 3
