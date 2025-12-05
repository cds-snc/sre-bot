"""Unit tests for DynamoDB idempotency cache."""

import pytest
import json
from unittest.mock import patch, MagicMock

from infrastructure.idempotency.dynamodb import DynamoDBCache
from infrastructure.operations.result import OperationResult, OperationStatus

pytestmark = pytest.mark.unit


class TestDynamoDBCacheInitialization:
    """Tests for DynamoDBCache initialization."""

    def test_cache_initializes_with_default_table(self):
        """DynamoDBCache initializes with default table name."""
        cache = DynamoDBCache()
        assert cache.table_name == "sre_bot_idempotency"

    def test_cache_initializes_with_custom_table(self):
        """DynamoDBCache initializes with custom table name."""
        cache = DynamoDBCache(table_name="custom_table")
        assert cache.table_name == "custom_table"

    def test_cache_loads_ttl_from_settings(self, monkeypatch):
        """DynamoDBCache loads TTL from settings."""
        # Mock settings to have specific TTL
        mock_settings = MagicMock()
        mock_settings.idempotency.IDEMPOTENCY_TTL_SECONDS = 7200
        monkeypatch.setattr(
            "infrastructure.idempotency.dynamodb.settings", mock_settings
        )

        cache = DynamoDBCache()
        assert cache.ttl_seconds == 7200


class TestDynamoDBCacheGet:
    """Tests for DynamoDBCache get method."""

    @patch("infrastructure.idempotency.dynamodb.get_item")
    def test_cache_get_returns_none_on_cache_miss(self, mock_get_item):
        """Cache get returns None for missing key."""
        mock_get_item.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="not found",
            data=None,
        )

        cache = DynamoDBCache()
        result = cache.get("missing-key")
        assert result is None

    @patch("infrastructure.idempotency.dynamodb.get_item")
    def test_cache_get_returns_response_on_cache_hit(self, mock_get_item):
        """Cache get returns cached response on hit."""
        response = {"success": True, "data": {"id": "123"}}
        mock_get_item.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="found",
            data={"Item": {"response_json": {"S": json.dumps(response)}}},
        )

        cache = DynamoDBCache()
        result = cache.get("existing-key")
        assert result == response

    @patch("infrastructure.idempotency.dynamodb.get_item")
    def test_cache_get_handles_dynamodb_error(self, mock_get_item):
        """Cache get returns None on DynamoDB error."""
        mock_get_item.return_value = OperationResult(
            status=OperationStatus.TRANSIENT_ERROR,
            message="Connection error",
            error_code="ServiceUnavailable",
        )

        cache = DynamoDBCache()
        result = cache.get("key")
        assert result is None

    @patch("infrastructure.idempotency.dynamodb.get_item")
    def test_cache_get_handles_json_decode_error(self, mock_get_item):
        """Cache get returns None on JSON decode error."""
        mock_get_item.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="found",
            data={"Item": {"response_json": {"S": "invalid json"}}},
        )

        cache = DynamoDBCache()
        result = cache.get("key")
        assert result is None


class TestDynamoDBCacheSet:
    """Tests for DynamoDBCache set method."""

    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_cache_set_stores_response(self, mock_put_item):
        """Cache set stores response with TTL."""
        mock_put_item.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="stored",
        )

        response = {"success": True, "data": {"id": "123"}}
        cache = DynamoDBCache()
        cache.set("key", response, ttl_seconds=3600)

        # Verify put_item was called
        mock_put_item.assert_called_once()
        call_args = mock_put_item.call_args
        assert call_args[1]["table_name"] == "sre_bot_idempotency"
        assert call_args[1]["Item"]["idempotency_key"]["S"] == "key"
        assert "response_json" in call_args[1]["Item"]
        assert "ttl" in call_args[1]["Item"]

    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_cache_set_uses_default_ttl_if_not_specified(self, mock_put_item):
        """Cache set uses default TTL when not specified."""
        mock_put_item.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="stored",
        )

        response = {"success": True}
        cache = DynamoDBCache()
        cache.ttl_seconds = 1800  # Set default to 30 minutes

        cache.set("key", response)

        call_args = mock_put_item.call_args
        # TTL should be current_time + 1800
        ttl_value = int(call_args[1]["Item"]["ttl"]["N"])
        import time

        assert ttl_value > int(time.time())  # TTL is in the future

    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_cache_set_handles_serialization_error(self, mock_put_item):
        """Cache set handles JSON serialization errors gracefully."""

        # Create an object that can't be JSON serialized
        class NonSerializable:
            pass

        response = NonSerializable()
        cache = DynamoDBCache()
        # Should not raise, just log error
        cache.set("key", response)

    @patch("infrastructure.idempotency.dynamodb.put_item")
    def test_cache_set_handles_dynamodb_error(self, mock_put_item):
        """Cache set handles DynamoDB errors gracefully."""
        mock_put_item.return_value = OperationResult(
            status=OperationStatus.TRANSIENT_ERROR,
            message="Write failed",
            error_code="ThrottlingException",
        )

        cache = DynamoDBCache()
        # Should not raise, just log error
        cache.set("key", {"success": True})


class TestDynamoDBCacheClear:
    """Tests for DynamoDBCache clear method."""

    @patch("infrastructure.idempotency.dynamodb.scan")
    @patch("infrastructure.idempotency.dynamodb.delete_item")
    def test_cache_clear_deletes_all_items(self, mock_delete, mock_scan):
        """Cache clear scans and deletes all items."""
        mock_scan.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="scanned",
            data={
                "Items": [
                    {"idempotency_key": {"S": "key1"}},
                    {"idempotency_key": {"S": "key2"}},
                ]
            },
        )
        mock_delete.return_value = OperationResult(
            status=OperationStatus.SUCCESS,
            message="deleted",
        )

        cache = DynamoDBCache()
        cache.clear()

        # Should have deleted 2 items
        assert mock_delete.call_count == 2

    @patch("infrastructure.idempotency.dynamodb.scan")
    def test_cache_clear_handles_scan_error(self, mock_scan):
        """Cache clear handles scan errors gracefully."""
        mock_scan.return_value = OperationResult(
            status=OperationStatus.TRANSIENT_ERROR,
            message="Scan failed",
            error_code="ServiceUnavailable",
        )

        cache = DynamoDBCache()
        # Should not raise, just log error
        cache.clear()


class TestDynamoDBCacheStats:
    """Tests for DynamoDBCache get_stats method."""

    def test_cache_stats_returns_backend_info(self):
        """Cache stats returns backend information."""
        cache = DynamoDBCache(table_name="test_table")
        stats = cache.get_stats()

        assert stats["backend"] == "dynamodb"
        assert stats["table_name"] == "test_table"
        assert "ttl_seconds" in stats
        assert stats["partition_key"] == "idempotency_key"

    def test_cache_stats_includes_ttl_seconds(self):
        """Cache stats includes configured TTL."""
        cache = DynamoDBCache()
        cache.ttl_seconds = 7200
        stats = cache.get_stats()

        assert stats["ttl_seconds"] == 7200
