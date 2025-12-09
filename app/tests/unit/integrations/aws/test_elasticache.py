"""Unit tests for AWS ElastiCache Redis client integration.

Tests cover:
- Connection pool creation and reuse
- Key-value operations (set, get, delete)
- TTL management
- JSON serialization/deserialization
- Error handling (connection, timeout, Redis errors)
- Health check operations
"""

import pytest
from unittest.mock import patch
from redis.exceptions import ConnectionError, TimeoutError, RedisError  # type: ignore

from integrations.aws.elasticache import (
    get_elasticache_client,
    set_value,
    get_value,
    delete_value,
    exists,
    get_ttl,
    health_check,
)


@pytest.mark.unit
class TestElastiCacheClientConnectionManagement:
    """Tests for ElastiCache client connection and pool management."""

    def test_creates_connection_pool_on_first_access(
        self,
        mock_connection_pool,
        mock_redis_client,
        mock_elasticache_settings,
        reset_elasticache_global_state,
    ):
        """Test that connection pool is created on first client access."""
        mock_redis_client.ping.return_value = True

        client = get_elasticache_client()

        assert client == mock_redis_client
        mock_connection_pool.assert_called_once()

    def test_reuses_existing_client_connection(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test that existing client is reused instead of creating new one."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client

        client = get_elasticache_client()

        assert client == mock_redis_client

    def test_handles_connection_error_on_initialization(
        self,
        mock_connection_pool,
        mock_elasticache_settings,
        reset_elasticache_global_state,
    ):
        """Test handling of connection errors during client initialization."""
        with patch("integrations.aws.elasticache.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = ConnectionError(
                "Connection failed"
            )

            with pytest.raises(ConnectionError):
                get_elasticache_client()


@pytest.mark.unit
class TestElastiCacheSetOperations:
    """Tests for setting values in ElastiCache."""

    def test_set_simple_string_value(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test setting a simple string value without TTL."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.set.return_value = True

        result = set_value("test_key", "test_value")

        assert result.is_success
        mock_redis_client.set.assert_called_once_with("test_key", "test_value")

    def test_set_dict_value_serializes_to_json(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test setting a dictionary value triggers JSON serialization."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.setex.return_value = True

        test_dict = {"state": "OPEN", "failure_count": 5}
        result = set_value("test_key", test_dict, ttl_seconds=3600)

        assert result.is_success
        mock_redis_client.setex.assert_called_once()
        call_args = mock_redis_client.setex.call_args[0]
        assert call_args[0] == "test_key"
        assert call_args[1] == 3600
        assert '"state": "OPEN"' in call_args[2]
        assert '"failure_count": 5' in call_args[2]

    def test_set_value_with_ttl_expiration(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test setting a value with TTL uses setex command."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.setex.return_value = True

        result = set_value("test_key", "test_value", ttl_seconds=300)

        assert result.is_success
        mock_redis_client.setex.assert_called_once_with("test_key", 300, "test_value")

    def test_set_handles_connection_error(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test handling of connection errors during set operation."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.set.side_effect = ConnectionError("Connection lost")

        result = set_value("test_key", "test_value")

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"
        assert "Connection lost" in result.message

    def test_set_handles_timeout_error(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test handling of timeout errors during set operation."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.set.side_effect = TimeoutError("Operation timed out")

        result = set_value("test_key", "test_value")

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"

    def test_set_handles_redis_error(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test handling of Redis-specific errors during set operation."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.set.side_effect = RedisError("Redis internal error")

        result = set_value("test_key", "test_value")

        assert not result.is_success
        assert result.error_code == "REDIS_ERROR"


@pytest.mark.unit
class TestElastiCacheGetOperations:
    """Tests for retrieving values from ElastiCache."""

    def test_get_existing_string_value(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test getting an existing string value."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.return_value = "test_value"

        result = get_value("test_key", deserialize_json=False)

        assert result.is_success
        assert result.data == "test_value"
        mock_redis_client.get.assert_called_once_with("test_key")

    def test_get_json_value_deserializes_automatically(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test getting and deserializing JSON value."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.return_value = '{"state": "OPEN", "failure_count": 5}'

        result = get_value("test_key", deserialize_json=True)

        assert result.is_success
        assert result.data == {"state": "OPEN", "failure_count": 5}

    def test_get_nonexistent_key_returns_none(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test getting a key that doesn't exist returns None."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.return_value = None

        result = get_value("nonexistent_key")

        assert result.is_success
        assert result.data is None

    def test_get_handles_connection_error(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test handling of connection errors during get operation."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.side_effect = ConnectionError("Connection lost")

        result = get_value("test_key")

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"

    def test_get_handles_invalid_json_gracefully(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test that invalid JSON returns as string instead of raising."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.return_value = "not-valid-json"

        result = get_value("test_key", deserialize_json=True)

        assert result.is_success
        assert result.data == "not-valid-json"


@pytest.mark.unit
class TestElastiCacheDeleteOperations:
    """Tests for deleting values from ElastiCache."""

    def test_delete_existing_key(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test deleting an existing key."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 1

        result = delete_value("test_key")

        assert result.is_success
        assert result.data["deleted"] is True
        mock_redis_client.delete.assert_called_once_with("test_key")

    def test_delete_nonexistent_key(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test deleting a key that doesn't exist."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 0

        result = delete_value("nonexistent_key")

        assert result.is_success
        assert result.data["deleted"] is False

    def test_delete_handles_connection_error(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test handling of connection errors during delete operation."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.delete.side_effect = ConnectionError("Connection lost")

        result = delete_value("test_key")

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"


@pytest.mark.unit
class TestElastiCacheExistenceChecks:
    """Tests for checking key existence in ElastiCache."""

    def test_exists_returns_true_for_existing_key(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test checking existence of an existing key."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.exists.return_value = 1

        result = exists("test_key")

        assert result.is_success
        assert result.data is True

    def test_exists_returns_false_for_nonexistent_key(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test checking existence of a non-existing key."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.exists.return_value = 0

        result = exists("nonexistent_key")

        assert result.is_success
        assert result.data is False


@pytest.mark.unit
class TestElastiCacheTTLOperations:
    """Tests for TTL management in ElastiCache."""

    def test_get_ttl_with_expiration_set(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test getting TTL for a key with expiration."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ttl.return_value = 300

        result = get_ttl("test_key")

        assert result.is_success
        assert result.data == 300

    def test_get_ttl_without_expiration_returns_negative_one(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test getting TTL for a key without expiration (-1)."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ttl.return_value = -1

        result = get_ttl("test_key")

        assert result.is_success
        assert result.data == -1

    def test_get_ttl_for_nonexistent_key_returns_negative_two(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test getting TTL for a non-existing key (-2)."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ttl.return_value = -2

        result = get_ttl("nonexistent_key")

        assert result.is_success
        assert result.data == -2


@pytest.mark.unit
class TestElastiCacheHealthCheck:
    """Tests for ElastiCache connection health checks."""

    def test_health_check_success_when_connected(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test successful health check when connection is healthy."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ping.return_value = True

        result = health_check()

        assert result.is_success
        mock_redis_client.ping.assert_called_once()

    def test_health_check_fails_on_connection_error(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test health check failure when connection is lost."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ping.side_effect = ConnectionError("Connection lost")

        result = health_check()

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"

    def test_health_check_fails_on_timeout(
        self, mock_redis_client, reset_elasticache_global_state
    ):
        """Test health check failure when ping times out."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ping.side_effect = TimeoutError("Ping timed out")

        result = health_check()

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"
