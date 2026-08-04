"""Unit tests for StorageService.

Tests serialization, deserialization, and error normalisation using a
mocked DynamoDBClient — no real AWS calls are made.
"""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from infrastructure.operations.result import OperationResult
from infrastructure.storage.service import DynamoDBStorageService


def _make_service() -> tuple[DynamoDBStorageService, MagicMock]:
    mock_dynamo = MagicMock()
    return DynamoDBStorageService(dynamodb=mock_dynamo), mock_dynamo


@pytest.mark.unit
class TestStorageServicePut:
    """Tests for StorageService.put."""

    def test_put_success(self):
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.success(data=None)

        result = service.put("my_table", {"pk": "abc", "name": "test"})

        assert result.is_success
        assert dynamo.put_item.called

    def test_put_serializes_item(self):
        """Plain Python values are converted to DynamoDB attribute format."""
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.success(data=None)

        service.put("my_table", {"pk": "abc", "count": 5, "active": True})

        kwargs = dynamo.put_item.call_args[1]
        item = kwargs["Item"]
        assert item["pk"] == {"S": "abc"}
        assert item["count"] == {"N": "5"}
        assert item["active"] == {"BOOL": True}

    def test_put_skips_none_values(self):
        """None-valued keys are excluded from the serialized item."""
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.success(data=None)

        service.put("my_table", {"pk": "abc", "optional_field": None})

        item = dynamo.put_item.call_args[1]["Item"]
        assert "optional_field" not in item
        assert "pk" in item

    def test_put_propagates_error(self):
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.permanent_error(
            message="Table not found", error_code="ResourceNotFoundException"
        )

        result = service.put("my_table", {"pk": "abc"})

        assert not result.is_success
        assert result.error_code == "ResourceNotFoundException"


@pytest.mark.unit
class TestStorageServicePutIfNotExists:
    """Tests for StorageService.put_if_not_exists."""

    def test_creates_item_returns_true(self):
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.success(data=None)

        result = service.put_if_not_exists("my_table", {"pk": "abc"}, pk_attribute="pk")

        assert result.is_success
        assert result.data is True

    def test_existing_item_returns_false(self):
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.permanent_error(
            message="Conflict",
            error_code="ConditionalCheckFailedException",
        )

        result = service.put_if_not_exists("my_table", {"pk": "abc"}, pk_attribute="pk")

        assert result.is_success
        assert result.data is False

    def test_uses_condition_expression(self):
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.success(data=None)

        service.put_if_not_exists("my_table", {"pk": "abc"}, pk_attribute="pk")

        kwargs = dynamo.put_item.call_args[1]
        assert kwargs.get("ConditionExpression") == "attribute_not_exists(pk)"

    def test_other_errors_propagate(self):
        service, dynamo = _make_service()
        dynamo.put_item.return_value = OperationResult.permanent_error(
            message="Access denied", error_code="AccessDeniedException"
        )

        result = service.put_if_not_exists("my_table", {"pk": "abc"}, pk_attribute="pk")

        assert not result.is_success
        assert result.error_code == "AccessDeniedException"


@pytest.mark.unit
class TestStorageServiceGet:
    """Tests for StorageService.get."""

    def test_get_returns_deserialized_item(self):
        service, dynamo = _make_service()
        dynamo.get_item.return_value = OperationResult.success(data={"Item": {"pk": {"S": "abc"}, "count": {"N": "5"}}})

        result = service.get("my_table", {"pk": "abc"})

        assert result.is_success
        assert result.data["pk"] == "abc"
        assert result.data["count"] == Decimal("5")

    def test_get_missing_item_returns_not_found(self):
        service, dynamo = _make_service()
        # DynamoDB returns empty dict (no "Item" key) when not found
        dynamo.get_item.return_value = OperationResult.success(data={})

        result = service.get("my_table", {"pk": "missing"})

        assert not result.is_success
        assert "not_found" in result.status.value

    def test_get_serializes_key(self):
        service, dynamo = _make_service()
        dynamo.get_item.return_value = OperationResult.success(data={"Item": {"pk": {"S": "abc"}}})

        service.get("my_table", {"pk": "abc"})

        key = dynamo.get_item.call_args[1]["Key"]
        assert key == {"pk": {"S": "abc"}}

    def test_get_propagates_dynamo_error(self):
        service, dynamo = _make_service()
        dynamo.get_item.return_value = OperationResult.permanent_error(message="Error", error_code="InternalServerError")

        result = service.get("my_table", {"pk": "abc"})

        assert not result.is_success


@pytest.mark.unit
class TestStorageServiceQuery:
    """Tests for StorageService.query."""

    def test_query_returns_deserialized_items(self):
        service, dynamo = _make_service()
        raw_items = [
            {"pk": {"S": "abc"}, "action": {"S": "created"}},
            {"pk": {"S": "abc"}, "action": {"S": "updated"}},
        ]
        dynamo.query.return_value = OperationResult.success(data=raw_items)

        result = service.query(
            "my_table",
            key_condition="pk = :pk",
            expression_values={":pk": "abc"},
        )

        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0]["pk"] == "abc"
        assert result.data[0]["action"] == "created"

    def test_query_serializes_expression_values(self):
        service, dynamo = _make_service()
        dynamo.query.return_value = OperationResult.success(data=[])

        service.query(
            "my_table",
            key_condition="pk = :pk",
            expression_values={":pk": "abc"},
        )

        kwargs = dynamo.query.call_args[1]
        assert kwargs["ExpressionAttributeValues"][":pk"] == {"S": "abc"}

    def test_query_passes_pagination_flags(self):
        service, dynamo = _make_service()
        dynamo.query.return_value = OperationResult.success(data=[])

        service.query(
            "my_table",
            key_condition="pk = :pk",
            expression_values={":pk": "abc"},
        )

        kwargs = dynamo.query.call_args[1]
        assert kwargs.get("force_paginate") is True
        assert kwargs.get("keys") == ["Items"]

    def test_query_passes_through_extra_kwargs(self):
        """IndexName, Limit, ScanIndexForward, etc. pass through to DynamoDBClient."""
        service, dynamo = _make_service()
        dynamo.query.return_value = OperationResult.success(data=[])

        service.query(
            "my_table",
            key_condition="pk = :pk",
            expression_values={":pk": "abc"},
            IndexName="my-gsi",
            Limit=10,
            ScanIndexForward=False,
        )

        kwargs = dynamo.query.call_args[1]
        assert kwargs.get("IndexName") == "my-gsi"
        assert kwargs.get("Limit") == 10
        assert kwargs.get("ScanIndexForward") is False

    def test_query_error_propagates(self):
        service, dynamo = _make_service()
        dynamo.query.return_value = OperationResult.permanent_error(message="Error", error_code="InternalServerError")

        result = service.query(
            "my_table",
            key_condition="pk = :pk",
            expression_values={":pk": "abc"},
        )

        assert not result.is_success


@pytest.mark.unit
class TestStorageServiceDelete:
    """Tests for StorageService.delete."""

    def test_delete_success(self):
        service, dynamo = _make_service()
        dynamo.delete_item.return_value = OperationResult.success(data=None)

        result = service.delete("my_table", {"pk": "abc"})

        assert result.is_success

    def test_delete_serializes_key(self):
        service, dynamo = _make_service()
        dynamo.delete_item.return_value = OperationResult.success(data=None)

        service.delete("my_table", {"pk": "abc"})

        key = dynamo.delete_item.call_args[1]["Key"]
        assert key == {"pk": {"S": "abc"}}

    def test_delete_propagates_error(self):
        service, dynamo = _make_service()
        dynamo.delete_item.return_value = OperationResult.permanent_error(message="Error", error_code="InternalServerError")

        result = service.delete("my_table", {"pk": "abc"})

        assert not result.is_success
