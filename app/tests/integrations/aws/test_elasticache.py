"""Tests for AWS ElastiCache integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from redis.exceptions import ConnectionError, TimeoutError, RedisError

from integrations.aws.elasticache import (
    get_elasticache_client,
    set_value,
    get_value,
    delete_value,
    exists,
    get_ttl,
    health_check,
)
from infrastructure.operations.result import OperationResult


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    with patch("integrations.aws.elasticache.Redis") as mock_redis:
        client = MagicMock()
        mock_redis.return_value = client
        yield client


@pytest.fixture
def mock_connection_pool():
    """Mock connection pool for testing."""
    with patch("integrations.aws.elasticache.ConnectionPool") as mock_pool:
        yield mock_pool


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("integrations.aws.elasticache.settings") as mock_settings:
        mock_settings.elasticache.ELASTICACHE_ENDPOINT = (
            "test-endpoint.cache.amazonaws.com"
        )
        mock_settings.elasticache.ELASTICACHE_PORT = 6379
        yield mock_settings


class TestGetElastiCacheClient:
    """Tests for get_elasticache_client."""

    def test_creates_connection_pool(
        self, mock_connection_pool, mock_redis_client, mock_settings
    ):
        """Test that connection pool is created on first access."""
        # Reset global state
        import integrations.aws.elasticache as ec

        ec._connection_pool = None
        ec._redis_client = None

        mock_redis_client.ping.return_value = True

        client = get_elasticache_client()

        assert client == mock_redis_client
        mock_connection_pool.assert_called_once()

    def test_reuses_existing_client(self, mock_redis_client):
        """Test that existing client is reused."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client

        client = get_elasticache_client()

        assert client == mock_redis_client

    def test_handles_connection_error(self, mock_connection_pool, mock_settings):
        """Test handling of connection errors."""
        import integrations.aws.elasticache as ec

        ec._connection_pool = None
        ec._redis_client = None

        with patch("integrations.aws.elasticache.Redis") as mock_redis:
            mock_redis.return_value.ping.side_effect = ConnectionError(
                "Connection failed"
            )

            with pytest.raises(ConnectionError):
                get_elasticache_client()


class TestSetValue:
    """Tests for set_value."""

    def test_set_simple_value(self, mock_redis_client):
        """Test setting a simple string value."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.set.return_value = True

        result = set_value("test_key", "test_value")

        assert result.is_success
        mock_redis_client.set.assert_called_once_with("test_key", "test_value")

    def test_set_dict_value(self, mock_redis_client):
        """Test setting a dictionary value (JSON serialization)."""
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

    def test_set_with_ttl(self, mock_redis_client):
        """Test setting a value with TTL."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.setex.return_value = True

        result = set_value("test_key", "test_value", ttl_seconds=300)

        assert result.is_success
        mock_redis_client.setex.assert_called_once_with("test_key", 300, "test_value")

    def test_set_connection_error(self, mock_redis_client):
        """Test handling of connection errors during set."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.set.side_effect = ConnectionError("Connection lost")

        result = set_value("test_key", "test_value")

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"

    def test_set_redis_error(self, mock_redis_client):
        """Test handling of Redis errors during set."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.set.side_effect = RedisError("Redis error")

        result = set_value("test_key", "test_value")

        assert not result.is_success
        assert result.error_code == "REDIS_ERROR"


class TestGetValue:
    """Tests for get_value."""

    def test_get_existing_value(self, mock_redis_client):
        """Test getting an existing value."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.return_value = "test_value"

        result = get_value("test_key", deserialize_json=False)

        assert result.is_success
        assert result.data == "test_value"

    def test_get_json_value(self, mock_redis_client):
        """Test getting and deserializing JSON value."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.return_value = '{"state": "OPEN", "failure_count": 5}'

        result = get_value("test_key", deserialize_json=True)

        assert result.is_success
        assert result.data == {"state": "OPEN", "failure_count": 5}

    def test_get_nonexistent_key(self, mock_redis_client):
        """Test getting a key that doesn't exist."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.return_value = None

        result = get_value("nonexistent_key")

        assert result.is_success
        assert result.data is None

    def test_get_connection_error(self, mock_redis_client):
        """Test handling of connection errors during get."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.get.side_effect = ConnectionError("Connection lost")

        result = get_value("test_key")

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"


class TestDeleteValue:
    """Tests for delete_value."""

    def test_delete_existing_key(self, mock_redis_client):
        """Test deleting an existing key."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 1

        result = delete_value("test_key")

        assert result.is_success
        assert result.data["deleted"] is True

    def test_delete_nonexistent_key(self, mock_redis_client):
        """Test deleting a key that doesn't exist."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.delete.return_value = 0

        result = delete_value("nonexistent_key")

        assert result.is_success
        assert result.data["deleted"] is False


class TestExists:
    """Tests for exists."""

    def test_key_exists(self, mock_redis_client):
        """Test checking existence of an existing key."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.exists.return_value = 1

        result = exists("test_key")

        assert result.is_success
        assert result.data is True

    def test_key_not_exists(self, mock_redis_client):
        """Test checking existence of a non-existing key."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.exists.return_value = 0

        result = exists("nonexistent_key")

        assert result.is_success
        assert result.data is False


class TestGetTTL:
    """Tests for get_ttl."""

    def test_get_ttl_with_expiration(self, mock_redis_client):
        """Test getting TTL for a key with expiration."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ttl.return_value = 300

        result = get_ttl("test_key")

        assert result.is_success
        assert result.data == 300

    def test_get_ttl_no_expiration(self, mock_redis_client):
        """Test getting TTL for a key without expiration."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ttl.return_value = -1

        result = get_ttl("test_key")

        assert result.is_success
        assert result.data == -1

    def test_get_ttl_key_not_exists(self, mock_redis_client):
        """Test getting TTL for a non-existing key."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ttl.return_value = -2

        result = get_ttl("nonexistent_key")

        assert result.is_success
        assert result.data == -2


class TestHealthCheck:
    """Tests for health_check."""

    def test_health_check_success(self, mock_redis_client):
        """Test successful health check."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ping.return_value = True

        result = health_check()

        assert result.is_success

    def test_health_check_connection_error(self, mock_redis_client):
        """Test health check with connection error."""
        import integrations.aws.elasticache as ec

        ec._redis_client = mock_redis_client
        mock_redis_client.ping.side_effect = ConnectionError("Connection lost")

        result = health_check()

        assert not result.is_success
        assert result.error_code == "CONNECTION_ERROR"
