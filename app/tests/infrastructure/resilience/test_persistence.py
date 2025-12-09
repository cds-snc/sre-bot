"""Tests for circuit breaker state persistence."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from infrastructure.resilience.persistence import CircuitBreakerStateStore
from infrastructure.operations.result import OperationResult


@pytest.fixture
def mock_elasticache_enabled():
    """Mock settings with ElastiCache enabled."""
    with patch("infrastructure.resilience.persistence.settings") as mock_settings:
        mock_settings.elasticache.ELASTICACHE_ENABLED = True
        yield mock_settings


@pytest.fixture
def mock_elasticache_disabled():
    """Mock settings with ElastiCache disabled."""
    with patch("infrastructure.resilience.persistence.settings") as mock_settings:
        mock_settings.elasticache.ELASTICACHE_ENABLED = False
        yield mock_settings


@pytest.fixture
def mock_elasticache_operations():
    """Mock ElastiCache operations."""
    with (
        patch("infrastructure.resilience.persistence.get_value") as mock_get,
        patch("infrastructure.resilience.persistence.set_value") as mock_set,
        patch("infrastructure.resilience.persistence.delete_value") as mock_delete,
        patch("infrastructure.resilience.persistence.exists") as mock_exists,
    ):

        yield {
            "get": mock_get,
            "set": mock_set,
            "delete": mock_delete,
            "exists": mock_exists,
        }


class TestCircuitBreakerStateStore:
    """Tests for CircuitBreakerStateStore."""

    def test_initialization_enabled(self, mock_elasticache_enabled):
        """Test initialization when ElastiCache is enabled."""
        store = CircuitBreakerStateStore()

        assert store.enabled is True
        assert store.key_prefix == "circuit_breaker"
        assert store.default_ttl_seconds == 3600

    def test_initialization_disabled(self, mock_elasticache_disabled):
        """Test initialization when ElastiCache is disabled."""
        store = CircuitBreakerStateStore()

        assert store.enabled is False

    def test_custom_configuration(self, mock_elasticache_enabled):
        """Test initialization with custom configuration."""
        store = CircuitBreakerStateStore(
            key_prefix="custom_prefix",
            default_ttl_seconds=7200,
        )

        assert store.key_prefix == "custom_prefix"
        assert store.default_ttl_seconds == 7200

    def test_make_key(self, mock_elasticache_enabled):
        """Test key generation."""
        store = CircuitBreakerStateStore()

        key = store._make_key("google_workspace")

        assert key == "circuit_breaker:google_workspace"

    def test_save_state_success(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test successfully saving state."""
        mock_elasticache_operations["set"].return_value = OperationResult.success(
            "Saved"
        )

        store = CircuitBreakerStateStore()
        state = {"state": "OPEN", "failure_count": 5}

        store.save_state("google_workspace", state)

        mock_elasticache_operations["set"].assert_called_once()
        call_args = mock_elasticache_operations["set"].call_args
        assert call_args[0][0] == "circuit_breaker:google_workspace"
        assert call_args[0][1]["state"] == "OPEN"
        assert call_args[0][1]["failure_count"] == 5
        assert "updated_at" in call_args[0][1]
        assert call_args[1]["ttl_seconds"] == 3600

    def test_save_state_disabled(
        self, mock_elasticache_disabled, mock_elasticache_operations
    ):
        """Test save_state when ElastiCache is disabled (no-op)."""
        store = CircuitBreakerStateStore()
        state = {"state": "OPEN", "failure_count": 5}

        store.save_state("google_workspace", state)

        mock_elasticache_operations["set"].assert_not_called()

    def test_save_state_error(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test handling of save errors."""
        mock_elasticache_operations["set"].return_value = (
            OperationResult.transient_error(
                "Connection error",
                error_code="CONNECTION_ERROR",
            )
        )

        store = CircuitBreakerStateStore()
        state = {"state": "OPEN", "failure_count": 5}

        # Should not raise, just log warning
        store.save_state("google_workspace", state)

    def test_load_state_success(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test successfully loading state."""
        saved_state = {
            "state": "OPEN",
            "failure_count": 5,
            "success_count": 0,
            "last_failure_time": "2023-10-01T12:00:00",
            "updated_at": "2023-10-01T12:00:00",
        }
        mock_elasticache_operations["get"].return_value = OperationResult.success(
            "Loaded",
            data=saved_state,
        )

        store = CircuitBreakerStateStore()

        result = store.load_state("google_workspace")

        assert result == saved_state
        mock_elasticache_operations["get"].assert_called_once_with(
            "circuit_breaker:google_workspace",
            deserialize_json=True,
        )

    def test_load_state_not_found(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test loading state when key doesn't exist."""
        mock_elasticache_operations["get"].return_value = OperationResult.success(
            "Not found",
            data=None,
        )

        store = CircuitBreakerStateStore()

        result = store.load_state("google_workspace")

        assert result is None

    def test_load_state_disabled(
        self, mock_elasticache_disabled, mock_elasticache_operations
    ):
        """Test load_state when ElastiCache is disabled."""
        store = CircuitBreakerStateStore()

        result = store.load_state("google_workspace")

        assert result is None
        mock_elasticache_operations["get"].assert_not_called()

    def test_load_state_error(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test handling of load errors."""
        mock_elasticache_operations["get"].return_value = (
            OperationResult.transient_error(
                "Connection error",
                error_code="CONNECTION_ERROR",
            )
        )

        store = CircuitBreakerStateStore()

        result = store.load_state("google_workspace")

        assert result is None

    def test_delete_state_success(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test successfully deleting state."""
        mock_elasticache_operations["delete"].return_value = OperationResult.success(
            "Deleted"
        )

        store = CircuitBreakerStateStore()

        store.delete_state("google_workspace")

        mock_elasticache_operations["delete"].assert_called_once_with(
            "circuit_breaker:google_workspace"
        )

    def test_delete_state_disabled(
        self, mock_elasticache_disabled, mock_elasticache_operations
    ):
        """Test delete_state when ElastiCache is disabled."""
        store = CircuitBreakerStateStore()

        store.delete_state("google_workspace")

        mock_elasticache_operations["delete"].assert_not_called()

    def test_exists_state_true(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test checking existence when state exists."""
        mock_elasticache_operations["exists"].return_value = OperationResult.success(
            "Exists",
            data=True,
        )

        store = CircuitBreakerStateStore()

        result = store.exists_state("google_workspace")

        assert result is True

    def test_exists_state_false(
        self, mock_elasticache_enabled, mock_elasticache_operations
    ):
        """Test checking existence when state doesn't exist."""
        mock_elasticache_operations["exists"].return_value = OperationResult.success(
            "Not exists",
            data=False,
        )

        store = CircuitBreakerStateStore()

        result = store.exists_state("google_workspace")

        assert result is False

    def test_exists_state_disabled(
        self, mock_elasticache_disabled, mock_elasticache_operations
    ):
        """Test exists_state when ElastiCache is disabled."""
        store = CircuitBreakerStateStore()

        result = store.exists_state("google_workspace")

        assert result is False
        mock_elasticache_operations["exists"].assert_not_called()
