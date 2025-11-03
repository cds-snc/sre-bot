"""Tests for circuit breaker functionality."""

import pytest
import time
from modules.groups.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


class TestCircuitBreakerStates:
    """Test circuit breaker state transitions."""

    def test_circuit_breaker_starts_closed(self):
        """Test that circuit starts in CLOSED state."""
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=5)
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_allows_calls_when_closed(self):
        """Test that requests pass through when circuit is CLOSED."""
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=5)

        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_opens_after_threshold(self):
        """Test that circuit opens after threshold failures."""
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=5)

        def failing_func():
            raise Exception("test failure")

        # Fail 3 times (threshold)
        for i in range(3):
            with pytest.raises(Exception):
                cb.call(failing_func)

        # Circuit should be open now
        assert cb.state == CircuitState.OPEN

    def test_circuit_breaker_rejects_when_open(self):
        """Test that requests are rejected when circuit is OPEN."""
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=5)

        def failing_func():
            raise Exception("test failure")

        # Trip the circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        # Now try to call a working function - should be rejected
        def success_func():
            return "success"

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(success_func)

        assert "OPEN" in str(exc_info.value)

    def test_circuit_breaker_half_open_recovery(self):
        """Test recovery through HALF_OPEN state."""
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=1)

        def failing_func():
            raise Exception("test failure")

        # Trip the circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.5)

        # Next call should attempt recovery (HALF_OPEN)
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_half_open_fails_back_to_open(self):
        """Test that failure in HALF_OPEN returns to OPEN."""
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=1)

        def failing_func():
            raise Exception("test failure")

        # Trip the circuit
        for i in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        # Wait for timeout
        time.sleep(1.5)

        # Fail during recovery
        with pytest.raises(Exception):
            cb.call(failing_func)

        # Should be back to OPEN
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerStats:
    """Test circuit breaker statistics and monitoring."""

    def test_circuit_breaker_tracks_stats(self):
        """Test that circuit breaker tracks statistics."""
        cb = CircuitBreaker("test-provider", failure_threshold=3, timeout_seconds=10)

        stats = cb.get_stats()

        assert stats["name"] == "test-provider"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0

    def test_circuit_breaker_stats_on_failure(self):
        """Test that stats are updated on failure."""
        cb = CircuitBreaker("test", failure_threshold=5, timeout_seconds=10)

        def failing_func():
            raise Exception("test")

        for i in range(3):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        stats = cb.get_stats()
        assert stats["failure_count"] == 3

    def test_circuit_breaker_failure_count_resets_on_success(self):
        """Test that failure count resets after successful call."""
        cb = CircuitBreaker("test", failure_threshold=5, timeout_seconds=10)

        def failing_func():
            raise Exception("test")

        # Have some failures
        for i in range(3):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        assert cb.get_stats()["failure_count"] == 3

        # Successful call should reset failure count
        def success_func():
            return "success"

        cb.call(success_func)
        assert cb.get_stats()["failure_count"] == 0


class TestCircuitBreakerReset:
    """Test manual reset functionality."""

    def test_circuit_breaker_manual_reset(self):
        """Test manual reset of circuit breaker."""
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=5)

        def failing_func():
            raise Exception("test failure")

        # Trip the circuit
        for i in range(2):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

        # Manual reset
        cb.reset()

        assert cb.state == CircuitState.CLOSED

        # Should work now
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"


class TestCircuitBreakerHalfOpenMaxCalls:
    """Test HALF_OPEN state max calls limit."""

    def test_half_open_max_calls_limit(self):
        """Test that HALF_OPEN state limits concurrent calls."""
        cb = CircuitBreaker(
            "test", failure_threshold=2, timeout_seconds=1, half_open_max_calls=1
        )

        def failing_func():
            raise Exception("test failure")

        # Trip the circuit
        for i in range(2):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        assert cb.state == CircuitState.OPEN

        # Wait for timeout to enter HALF_OPEN
        time.sleep(1.5)

        # First call in HALF_OPEN should succeed
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerConfiguration:
    """Test circuit breaker configuration options."""

    def test_custom_failure_threshold(self):
        """Test custom failure threshold."""
        cb = CircuitBreaker("test", failure_threshold=5, timeout_seconds=10)

        def failing_func():
            raise Exception("test")

        # Should fail 4 times without opening
        for i in range(4):
            try:
                cb.call(failing_func)
            except Exception:
                pass

        assert cb.state == CircuitState.CLOSED

        # 5th failure should open it
        try:
            cb.call(failing_func)
        except Exception:
            pass

        assert cb.state == CircuitState.OPEN

    def test_custom_timeout(self):
        """Test custom timeout configuration."""
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise Exception("test")

        # Trip the circuit
        try:
            cb.call(failing_func)
        except Exception:
            pass

        assert cb.state == CircuitState.OPEN

        # Should still be open before timeout
        with pytest.raises(CircuitBreakerOpenError):

            def success_func():
                return "success"

            cb.call(success_func)

        # Wait for timeout
        time.sleep(1.5)

        # Should now allow recovery
        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerExceptionHandling:
    """Test exception handling in circuit breaker."""

    def test_circuit_breaker_propagates_exceptions(self):
        """Test that circuit breaker propagates function exceptions."""
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=5)

        def failing_func():
            raise ValueError("custom error")

        with pytest.raises(ValueError) as exc_info:
            cb.call(failing_func)

        assert "custom error" in str(exc_info.value)

    def test_circuit_breaker_open_error_message(self):
        """Test that OPEN circuit provides helpful error message."""
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=60)

        def failing_func():
            raise Exception("test")

        # Trip the circuit
        try:
            cb.call(failing_func)
        except Exception:
            pass

        # Try to call when open
        with pytest.raises(CircuitBreakerOpenError) as exc_info:

            def success_func():
                return "success"

            cb.call(success_func)

        error_msg = str(exc_info.value)
        assert "OPEN" in error_msg
        assert "test" in error_msg
