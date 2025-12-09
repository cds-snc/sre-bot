"""Fixtures for AWS integrations tests.

Level: Component-level fixtures for AWS integrations
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing ElastiCache operations."""
    with patch("integrations.aws.elasticache.Redis") as mock_redis:
        client = MagicMock()
        mock_redis.return_value = client
        yield client


@pytest.fixture
def mock_connection_pool():
    """Mock Redis connection pool for testing."""
    with patch("integrations.aws.elasticache.ConnectionPool") as mock_pool:
        yield mock_pool


@pytest.fixture
def mock_elasticache_settings(monkeypatch):
    """Mock ElastiCache settings for testing."""
    mock_settings = MagicMock()
    mock_settings.elasticache.ELASTICACHE_ENDPOINT = "test-endpoint.cache.amazonaws.com"
    mock_settings.elasticache.ELASTICACHE_PORT = 6379
    monkeypatch.setattr("integrations.aws.elasticache.settings", mock_settings)
    return mock_settings


@pytest.fixture
def reset_elasticache_global_state():
    """Reset ElastiCache global connection state between tests.

    Use this fixture when tests need isolated connection state.
    """
    import integrations.aws.elasticache as ec

    # Store original state
    original_pool = ec._connection_pool
    original_client = ec._redis_client

    # Reset to None
    ec._connection_pool = None
    ec._redis_client = None

    yield

    # Restore original state
    ec._connection_pool = original_pool
    ec._redis_client = original_client
