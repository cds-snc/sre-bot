"""Fixtures for infrastructure resilience tests.

Level: Component-level fixtures for resilience module
"""

import pytest
from unittest.mock import MagicMock
from infrastructure.operations.result import OperationResult


@pytest.fixture
def mock_elasticache_enabled(monkeypatch):
    """Mock settings with ElastiCache enabled."""
    mock_settings = MagicMock()
    mock_settings.elasticache.ELASTICACHE_ENABLED = True
    monkeypatch.setattr("infrastructure.resilience.persistence.settings", mock_settings)
    return mock_settings


@pytest.fixture
def mock_elasticache_disabled(monkeypatch):
    """Mock settings with ElastiCache disabled."""
    mock_settings = MagicMock()
    mock_settings.elasticache.ELASTICACHE_ENABLED = False
    monkeypatch.setattr("infrastructure.resilience.persistence.settings", mock_settings)
    return mock_settings


@pytest.fixture
def mock_elasticache_get(monkeypatch):
    """Mock ElastiCache get_value operation."""
    mock_get = MagicMock()
    monkeypatch.setattr("infrastructure.resilience.persistence.get_value", mock_get)
    return mock_get


@pytest.fixture
def mock_elasticache_set(monkeypatch):
    """Mock ElastiCache set_value operation."""
    mock_set = MagicMock()
    monkeypatch.setattr("infrastructure.resilience.persistence.set_value", mock_set)
    return mock_set


@pytest.fixture
def mock_elasticache_delete(monkeypatch):
    """Mock ElastiCache delete_value operation."""
    mock_delete = MagicMock()
    monkeypatch.setattr(
        "infrastructure.resilience.persistence.delete_value", mock_delete
    )
    return mock_delete


@pytest.fixture
def mock_elasticache_exists(monkeypatch):
    """Mock ElastiCache exists operation."""
    mock_exists = MagicMock()
    monkeypatch.setattr("infrastructure.resilience.persistence.exists", mock_exists)
    return mock_exists


@pytest.fixture
def circuit_breaker_state_factory():
    """Factory for creating circuit breaker state dictionaries.

    Returns:
        Factory function that creates state dictionaries
    """
    from tests.factories.resilience import make_circuit_breaker_state

    return make_circuit_breaker_state


@pytest.fixture
def elasticache_key_factory():
    """Factory for creating ElastiCache keys.

    Returns:
        Factory function that creates Redis keys
    """
    from tests.factories.resilience import make_elasticache_key

    return make_elasticache_key
