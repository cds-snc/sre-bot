"""Integration tests for DynamoDB idempotency cache.

These tests verify the cache behavior with mocked DynamoDB operations.
For true integration tests with real DynamoDB, use local DynamoDB or
AWS DynamoDB with test tables.
"""

import pytest
import json
from unittest.mock import patch

from infrastructure.idempotency.dynamodb import DynamoDBCache
from infrastructure.operations.result import OperationResult, OperationStatus

pytestmark = pytest.mark.integration


class TestDynamoDBCacheIntegration:
    """Integration tests for DynamoDB cache."""

    @patch("infrastructure.idempotency.dynamodb.get_item")
    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_cache_roundtrip_store_and_retrieve(self, mock_put, mock_get):
        """Test storing and retrieving a response from cache."""
        response_data = {
            "success": True,
            "status_code": 200,
            "data": {"id": "123", "name": "test"},
        }

        # Mock successful put
        mock_put.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item stored",
        )

        # Mock successful get
        mock_get.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item retrieved",
            data={"Item": {"response_json": {"S": json.dumps(response_data)}}},
        )

        cache = DynamoDBCache()

        # Store response
        cache.set("test-key", response_data, ttl_seconds=3600)
        assert mock_put.called

        # Retrieve response
        result = cache.get("test-key")
        assert result == response_data

    @patch("infrastructure.idempotency.dynamodb.get_item")
    def test_cache_json_serialization_with_complex_response(self, mock_get):
        """Test cache handles complex nested responses."""
        complex_response = {
            "success": True,
            "metadata": {
                "timestamp": "2025-01-01T00:00:00Z",
                "request_id": "req-123",
            },
            "data": {
                "items": [
                    {"id": "1", "status": "active"},
                    {"id": "2", "status": "pending"},
                ],
                "counts": {"total": 2, "active": 1},
            },
        }

        mock_get.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item retrieved",
            data={"Item": {"response_json": {"S": json.dumps(complex_response)}}},
        )

        cache = DynamoDBCache()
        result = cache.get("complex-key")

        assert result == complex_response
        assert result["metadata"]["request_id"] == "req-123"
        assert len(result["data"]["items"]) == 2

    @patch("infrastructure.idempotency.dynamodb.scan")
    @patch("infrastructure.idempotency.dynamodb.delete_item")
    def test_cache_clear_removes_all_entries(self, mock_delete, mock_scan):
        """Test cache clear removes all entries."""
        mock_scan.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Scanned",
            data={
                "Items": [
                    {"idempotency_key": {"S": "key-1"}},
                    {"idempotency_key": {"S": "key-2"}},
                    {"idempotency_key": {"S": "key-3"}},
                ]
            },
        )
        mock_delete.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Deleted",
        )

        cache = DynamoDBCache()
        cache.clear()

        # Verify delete was called for each item
        assert mock_delete.call_count == 3

    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_cache_uses_correct_dynamodb_format(self, mock_put):
        """Test cache uses correct DynamoDB attribute format."""
        mock_put.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Stored",
        )

        response_data = {"success": True, "value": 42}
        cache = DynamoDBCache()
        cache.set("test-key", response_data, ttl_seconds=1800)

        # Verify put_item was called with correct DynamoDB format
        call_args = mock_put.call_args
        item = call_args[1]["Item"]

        # Check structure of DynamoDB item
        assert "idempotency_key" in item
        assert item["idempotency_key"]["S"] == "test-key"

        assert "response_json" in item
        assert item["response_json"]["S"] == json.dumps(response_data)

        assert "ttl" in item
        assert "N" in item["ttl"]

        assert "created_at" in item
        assert "N" in item["created_at"]

        assert "operation_type" in item
        assert item["operation_type"]["S"] == "api_response"

    @patch("infrastructure.idempotency.dynamodb.get_item")
    def test_cache_handles_missing_item_attribute(self, mock_get):
        """Test cache handles response with missing Item attribute."""
        mock_get.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Item not found",
            data={},  # Missing Item key
        )

        cache = DynamoDBCache()
        result = cache.get("nonexistent-key")

        assert result is None

    def test_cache_stats_contains_all_fields(self):
        """Test cache stats contains all required fields."""
        cache = DynamoDBCache(table_name="custom_table")
        cache.ttl_seconds = 7200

        stats = cache.get_stats()

        assert stats["backend"] == "dynamodb"
        assert stats["table_name"] == "custom_table"
        assert stats["ttl_seconds"] == 7200
        assert stats["partition_key"] == "idempotency_key"

    @patch("infrastructure.idempotency.dynamodb.put_item")
    @patch("infrastructure.idempotency.dynamodb.get_item")
    def test_cache_multiple_operations_same_table(self, mock_get, mock_put):
        """Test cache handles multiple operations on same table."""
        mock_put.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="Stored",
        )

        response1 = {"id": "1", "data": "first"}
        response2 = {"id": "2", "data": "second"}

        mock_get.side_effect = [
            OperationResult(
                status=OperationStatus.SUCCESS,
                message="Found",
                data={"Item": {"response_json": {"S": json.dumps(response1)}}},
            ),
            OperationResult(
                status=OperationStatus.SUCCESS,
                message="Found",
                data={"Item": {"response_json": {"S": json.dumps(response2)}}},
            ),
        ]

        cache = DynamoDBCache()

        # Store two responses
        cache.set("key-1", response1)
        cache.set("key-2", response2)

        # Retrieve both
        result1 = cache.get("key-1")
        result2 = cache.get("key-2")

        assert result1 == response1
        assert result2 == response2
        assert mock_put.call_count == 2
        assert mock_get.call_count == 2
