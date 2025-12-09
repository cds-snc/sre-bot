"""Unit tests for circuit breaker state persistence.

Tests cover:
- State store initialization (enabled/disabled)
- State save operations with TTL
- State load operations with JSON deserialization
- State delete operations
- State existence checks
- Graceful degradation when ElastiCache is disabled
- Error handling for connection and Redis errors
"""

import pytest
from infrastructure.resilience.persistence import CircuitBreakerStateStore
from infrastructure.operations.result import OperationResult


@pytest.mark.unit
class TestCircuitBreakerStateStoreInitialization:
    """Tests for CircuitBreakerStateStore initialization and configuration."""

    def test_initialization_with_elasticache_enabled(self, mock_elasticache_enabled):
        """Test initialization when ElastiCache is enabled."""
        store = CircuitBreakerStateStore()

        assert store.enabled is True
        assert store.key_prefix == "circuit_breaker"
        assert store.default_ttl_seconds == 3600

    def test_initialization_with_elasticache_disabled(self, mock_elasticache_disabled):
        """Test initialization when ElastiCache is disabled."""
        store = CircuitBreakerStateStore()

        assert store.enabled is False
        assert store.key_prefix == "circuit_breaker"
        assert store.default_ttl_seconds == 3600

    def test_initialization_with_custom_configuration(self, mock_elasticache_enabled):
        """Test initialization with custom key prefix and TTL."""
        store = CircuitBreakerStateStore(
            key_prefix="custom_prefix",
            default_ttl_seconds=7200,
        )

        assert store.enabled is True
        assert store.key_prefix == "custom_prefix"
        assert store.default_ttl_seconds == 7200

    def test_make_key_generates_correct_format(
        self, mock_elasticache_enabled, elasticache_key_factory
    ):
        """Test Redis key generation follows expected pattern."""
        store = CircuitBreakerStateStore()

        key = store._make_key("google_workspace")
        expected_key = elasticache_key_factory("google_workspace")

        assert key == expected_key
        assert key == "circuit_breaker:google_workspace"

    def test_make_key_with_custom_prefix(self, mock_elasticache_enabled):
        """Test key generation with custom prefix."""
        store = CircuitBreakerStateStore(key_prefix="cb_state")

        key = store._make_key("aws_identity_center")

        assert key == "cb_state:aws_identity_center"


@pytest.mark.unit
class TestCircuitBreakerStateStoreSaveOperations:
    """Tests for saving circuit breaker state to ElastiCache."""

    def test_save_state_success(
        self,
        mock_elasticache_enabled,
        mock_elasticache_set,
        circuit_breaker_state_factory,
    ):
        """Test successfully saving state to ElastiCache."""
        mock_elasticache_set.return_value = OperationResult.success("Saved")

        store = CircuitBreakerStateStore()
        state = circuit_breaker_state_factory(state="OPEN", failure_count=5)

        store.save_state("google_workspace", state)

        mock_elasticache_set.assert_called_once()
        call_args = mock_elasticache_set.call_args
        assert call_args[0][0] == "circuit_breaker:google_workspace"
        assert call_args[0][1]["state"] == "OPEN"
        assert call_args[0][1]["failure_count"] == 5
        assert "updated_at" in call_args[0][1]
        assert call_args[1]["ttl_seconds"] == 3600

    def test_save_state_with_custom_ttl(
        self,
        mock_elasticache_enabled,
        mock_elasticache_set,
        circuit_breaker_state_factory,
    ):
        """Test saving state with custom TTL."""
        mock_elasticache_set.return_value = OperationResult.success("Saved")

        store = CircuitBreakerStateStore(default_ttl_seconds=1800)
        state = circuit_breaker_state_factory(state="HALF_OPEN")

        store.save_state("aws_identity_center", state)

        call_args = mock_elasticache_set.call_args
        assert call_args[1]["ttl_seconds"] == 1800

    def test_save_state_when_disabled_is_noop(
        self, mock_elasticache_disabled, mock_elasticache_set
    ):
        """Test save_state when ElastiCache is disabled performs no-op."""
        store = CircuitBreakerStateStore()
        state = {"state": "OPEN", "failure_count": 5}

        store.save_state("google_workspace", state)

        mock_elasticache_set.assert_not_called()

    def test_save_state_handles_connection_error_gracefully(
        self,
        mock_elasticache_enabled,
        mock_elasticache_set,
        circuit_breaker_state_factory,
    ):
        """Test save handles connection errors without raising."""
        mock_elasticache_set.return_value = OperationResult.transient_error(
            "Connection error",
            error_code="CONNECTION_ERROR",
        )

        store = CircuitBreakerStateStore()
        state = circuit_breaker_state_factory(state="OPEN")

        # Should not raise exception, just log warning
        store.save_state("google_workspace", state)

        mock_elasticache_set.assert_called_once()

    def test_save_state_handles_redis_error_gracefully(
        self,
        mock_elasticache_enabled,
        mock_elasticache_set,
        circuit_breaker_state_factory,
    ):
        """Test save handles Redis errors without raising."""
        mock_elasticache_set.return_value = OperationResult.permanent_error(
            "Redis error",
            error_code="REDIS_ERROR",
        )

        store = CircuitBreakerStateStore()
        state = circuit_breaker_state_factory(state="OPEN")

        # Should not raise exception
        store.save_state("google_workspace", state)

        mock_elasticache_set.assert_called_once()


@pytest.mark.unit
class TestCircuitBreakerStateStoreLoadOperations:
    """Tests for loading circuit breaker state from ElastiCache."""

    def test_load_state_success(
        self,
        mock_elasticache_enabled,
        mock_elasticache_get,
        circuit_breaker_state_factory,
    ):
        """Test successfully loading state from ElastiCache."""
        saved_state = circuit_breaker_state_factory(
            state="OPEN",
            failure_count=5,
            success_count=0,
            last_failure_time="2023-10-01T12:00:00",
            updated_at="2023-10-01T12:00:00",
        )
        mock_elasticache_get.return_value = OperationResult.success(
            "Loaded",
            data=saved_state,
        )

        store = CircuitBreakerStateStore()
        result = store.load_state("google_workspace")

        assert result == saved_state
        assert result["state"] == "OPEN"
        assert result["failure_count"] == 5
        mock_elasticache_get.assert_called_once_with(
            "circuit_breaker:google_workspace",
            deserialize_json=True,
        )

    def test_load_state_returns_none_when_not_found(
        self, mock_elasticache_enabled, mock_elasticache_get
    ):
        """Test loading state when key doesn't exist returns None."""
        mock_elasticache_get.return_value = OperationResult.success(
            "Not found",
            data=None,
        )

        store = CircuitBreakerStateStore()
        result = store.load_state("nonexistent_provider")

        assert result is None
        mock_elasticache_get.assert_called_once()

    def test_load_state_when_disabled_returns_none(
        self, mock_elasticache_disabled, mock_elasticache_get
    ):
        """Test load_state when ElastiCache is disabled returns None."""
        store = CircuitBreakerStateStore()

        result = store.load_state("google_workspace")

        assert result is None
        mock_elasticache_get.assert_not_called()

    def test_load_state_handles_connection_error_gracefully(
        self, mock_elasticache_enabled, mock_elasticache_get
    ):
        """Test load handles connection errors and returns None."""
        mock_elasticache_get.return_value = OperationResult.transient_error(
            "Connection error",
            error_code="CONNECTION_ERROR",
        )

        store = CircuitBreakerStateStore()
        result = store.load_state("google_workspace")

        assert result is None
        mock_elasticache_get.assert_called_once()

    def test_load_state_handles_redis_error_gracefully(
        self, mock_elasticache_enabled, mock_elasticache_get
    ):
        """Test load handles Redis errors and returns None."""
        mock_elasticache_get.return_value = OperationResult.permanent_error(
            "Redis error",
            error_code="REDIS_ERROR",
        )

        store = CircuitBreakerStateStore()
        result = store.load_state("google_workspace")

        assert result is None

    def test_load_state_with_custom_key_prefix(
        self, mock_elasticache_enabled, mock_elasticache_get
    ):
        """Test loading state with custom key prefix."""
        mock_elasticache_get.return_value = OperationResult.success(
            "Loaded", data={"state": "CLOSED"}
        )

        store = CircuitBreakerStateStore(key_prefix="cb_state")
        store.load_state("google_workspace")

        mock_elasticache_get.assert_called_once_with(
            "cb_state:google_workspace",
            deserialize_json=True,
        )


@pytest.mark.unit
class TestCircuitBreakerStateStoreDeleteOperations:
    """Tests for deleting circuit breaker state from ElastiCache."""

    def test_delete_state_success(
        self, mock_elasticache_enabled, mock_elasticache_delete
    ):
        """Test successfully deleting state from ElastiCache."""
        mock_elasticache_delete.return_value = OperationResult.success("Deleted")

        store = CircuitBreakerStateStore()
        store.delete_state("google_workspace")

        mock_elasticache_delete.assert_called_once_with(
            "circuit_breaker:google_workspace"
        )

    def test_delete_state_when_disabled_is_noop(
        self, mock_elasticache_disabled, mock_elasticache_delete
    ):
        """Test delete_state when ElastiCache is disabled performs no-op."""
        store = CircuitBreakerStateStore()

        store.delete_state("google_workspace")

        mock_elasticache_delete.assert_not_called()

    def test_delete_state_handles_errors_gracefully(
        self, mock_elasticache_enabled, mock_elasticache_delete
    ):
        """Test delete handles errors without raising."""
        mock_elasticache_delete.return_value = OperationResult.permanent_error(
            "Delete failed",
            error_code="REDIS_ERROR",
        )

        store = CircuitBreakerStateStore()

        # Should not raise exception
        store.delete_state("google_workspace")

        mock_elasticache_delete.assert_called_once()


@pytest.mark.unit
class TestCircuitBreakerStateStoreExistenceChecks:
    """Tests for checking circuit breaker state existence in ElastiCache."""

    def test_exists_state_returns_true_when_exists(
        self, mock_elasticache_enabled, mock_elasticache_exists
    ):
        """Test exists_state returns True when state exists."""
        mock_elasticache_exists.return_value = OperationResult.success(
            "Exists",
            data=True,
        )

        store = CircuitBreakerStateStore()
        result = store.exists_state("google_workspace")

        assert result is True
        mock_elasticache_exists.assert_called_once()

    def test_exists_state_returns_false_when_not_exists(
        self, mock_elasticache_enabled, mock_elasticache_exists
    ):
        """Test exists_state returns False when state doesn't exist."""
        mock_elasticache_exists.return_value = OperationResult.success(
            "Not exists",
            data=False,
        )

        store = CircuitBreakerStateStore()
        result = store.exists_state("google_workspace")

        assert result is False

    def test_exists_state_when_disabled_returns_false(
        self, mock_elasticache_disabled, mock_elasticache_exists
    ):
        """Test exists_state when ElastiCache is disabled returns False."""
        store = CircuitBreakerStateStore()

        result = store.exists_state("google_workspace")

        assert result is False
        mock_elasticache_exists.assert_not_called()

    def test_exists_state_handles_errors_gracefully(
        self, mock_elasticache_enabled, mock_elasticache_exists
    ):
        """Test exists_state handles errors and returns False."""
        mock_elasticache_exists.return_value = OperationResult.transient_error(
            "Connection error",
            error_code="CONNECTION_ERROR",
        )

        store = CircuitBreakerStateStore()
        result = store.exists_state("google_workspace")

        assert result is False
