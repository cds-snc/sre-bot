"""Unit tests for infrastructure circuit breaker functionality.

Moved from tests/unit/modules/groups/test_circuit_breaker.py.
"""

import pytest
import time
from infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


@pytest.mark.unit
class TestCircuitBreakerInitialization:
    """Tests for CircuitBreaker initialization."""

    def test_starts_in_closed_state(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)
        assert cb.state == CircuitState.CLOSED

    def test_initializes_with_zero_stats(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)
        stats = cb.get_stats()
        assert stats["failure_count"] == 0
        assert stats["success_count"] == 0

    def test_stores_configuration(self):
        cb = CircuitBreaker(
            "my-provider",
            failure_threshold=5,
            timeout_seconds=30,
            half_open_max_calls=2,
        )
        assert cb.name == "my-provider"
        assert cb.failure_threshold == 5
        assert cb.timeout_seconds == 30
        assert cb.half_open_max_calls == 2

    def test_default_configuration(self):
        cb = CircuitBreaker("test")
        assert cb.failure_threshold == 5
        assert cb.timeout_seconds == 60
        assert cb.half_open_max_calls == 3


@pytest.mark.unit
class TestCircuitBreakerClosedState:
    """Tests for CircuitBreaker CLOSED state behavior."""

    def test_allows_successful_calls(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def success_func():
            return "success"

        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_tracks_successful_calls(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)
        assert cb.state.value == "open"

        time.sleep(1.2)

        def success_func():
            return "ok"

        result = cb.call(success_func)
        assert result == "ok"
        assert cb.state.value == "closed"

    def test_propagates_function_exceptions(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError) as exc_info:
            cb.call(failing_func)
        assert "test error" in str(exc_info.value)

    def test_tracks_failures_in_closed_state(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        stats = cb.get_stats()
        assert stats["failure_count"] == 2

    def test_resets_failure_count_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        def success_func():
            return "ok"

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        assert cb.get_stats()["failure_count"] == 2

        cb.call(success_func)
        assert cb.get_stats()["failure_count"] == 0


@pytest.mark.unit
class TestCircuitBreakerOpenState:
    """Tests for CircuitBreaker OPEN state behavior."""

    def test_opens_after_failure_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        for _ in range(3):
            with pytest.raises(Exception):
                cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

    def test_rejects_calls_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        def success_func():
            return "ok"

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(success_func)

    def test_open_error_includes_circuit_name(self):
        cb = CircuitBreaker("test-provider", failure_threshold=1, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        with pytest.raises(CircuitBreakerOpenError) as exc_info:

            def success_func():
                return "ok"

            cb.call(success_func)

        assert "test-provider" in str(exc_info.value)

    def test_open_error_states_circuit_is_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        with pytest.raises(CircuitBreakerOpenError) as exc_info:

            def success_func():
                return "ok"

            cb.call(success_func)

        assert "OPEN" in str(exc_info.value)


@pytest.mark.unit
class TestCircuitBreakerHalfOpenState:
    """Tests for CircuitBreaker HALF_OPEN state behavior."""

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        time.sleep(1.5)

        def success_func():
            return "ok"

        result = cb.call(success_func)
        assert result == "ok"

    def test_closes_after_successful_half_open_call(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        time.sleep(1.5)

        def success_func():
            return "ok"

        cb.call(success_func)
        assert cb.state == CircuitState.CLOSED

    def test_reopens_after_failed_half_open_call(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        time.sleep(1.5)

        with pytest.raises(Exception):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

    def test_respects_half_open_max_calls(self):
        cb = CircuitBreaker(
            "test",
            failure_threshold=1,
            timeout_seconds=1,
            half_open_max_calls=1,
        )

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        time.sleep(1.5)

        def success_func():
            return "ok"

        result = cb.call(success_func)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED


@pytest.mark.unit
class TestCircuitBreakerReset:
    """Tests for CircuitBreaker manual reset functionality."""

    def test_reset_clears_state(self):
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=2, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        cb.reset()
        stats = cb.get_stats()
        assert stats["failure_count"] == 0

    def test_allows_calls_after_reset(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        cb.reset()

        def success_func():
            return "ok"

        result = cb.call(success_func)
        assert result == "ok"


@pytest.mark.unit
class TestCircuitBreakerStatistics:
    """Tests for CircuitBreaker statistics tracking."""

    def test_get_stats_returns_dict(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)
        stats = cb.get_stats()
        assert isinstance(stats, dict)

    def test_stats_includes_name(self):
        cb = CircuitBreaker("my-circuit", failure_threshold=3, timeout_seconds=60)
        stats = cb.get_stats()
        assert stats["name"] == "my-circuit"

    def test_stats_includes_state(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)
        stats = cb.get_stats()
        assert "state" in stats
        assert stats["state"] == "closed"

    def test_stats_includes_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        for _ in range(2):
            with pytest.raises(Exception):
                cb.call(failing_func)

        stats = cb.get_stats()
        assert stats["failure_count"] == 2

    def test_stats_includes_success_count(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        time.sleep(1.2)

        def success_func():
            return "ok"

        result = cb.call(success_func)
        assert result == "ok"

        stats = cb.get_stats()
        assert "success_count" in stats
        assert stats["success_count"] == 0

    def test_stats_includes_last_error_time(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=60)

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            cb.call(failing_func)

        stats = cb.get_stats()
        assert "last_failure_time" in stats
        assert stats["last_failure_time"] is not None


@pytest.mark.unit
class TestCircuitBreakerExceptionHandling:
    """Tests for CircuitBreaker exception handling."""

    def test_propagates_custom_exceptions(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        class CustomError(Exception):
            pass

        def failing_func():
            raise CustomError("custom")

        with pytest.raises(CustomError):
            cb.call(failing_func)

    def test_propagates_exception_messages(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def failing_func():
            raise ValueError("detailed error message")

        with pytest.raises(ValueError) as exc_info:
            cb.call(failing_func)

        assert "detailed error message" in str(exc_info.value)

    def test_handles_function_with_args(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def add(a, b):
            return a + b

        result = cb.call(add, 2, 3)
        assert result == 5

    def test_handles_function_with_kwargs(self):
        cb = CircuitBreaker("test", failure_threshold=3, timeout_seconds=60)

        def greet(name, greeting="Hello"):
            return f"{greeting} {name}"

        result = cb.call(greet, name="Alice", greeting="Hi")
        assert result == "Hi Alice"


@pytest.mark.unit
class TestCircuitBreakerConfiguration:
    """Tests for CircuitBreaker configuration options."""

    def test_custom_failure_threshold_respected(self):
        cb = CircuitBreaker("test", failure_threshold=5, timeout_seconds=60)

        def failing_func():
            raise Exception("fail")

        for _ in range(4):
            with pytest.raises(Exception):
                cb.call(failing_func)

        assert cb.state == CircuitState.CLOSED

        with pytest.raises(Exception):
            cb.call(failing_func)

        assert cb.state == CircuitState.OPEN

    def test_custom_timeout_respected(self):
        cb = CircuitBreaker("test", failure_threshold=1, timeout_seconds=1)

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        with pytest.raises(CircuitBreakerOpenError):

            def success_func():
                return "ok"

            cb.call(success_func)

        time.sleep(1.5)

        result = cb.call(success_func)
        assert result == "ok"

    def test_custom_half_open_max_calls_respected(self):
        cb = CircuitBreaker(
            "test",
            failure_threshold=1,
            timeout_seconds=1,
            half_open_max_calls=2,
        )

        def failing_func():
            raise Exception("fail")

        with pytest.raises(Exception):
            cb.call(failing_func)

        time.sleep(1.5)

        def success_func():
            return "ok"

        cb.call(success_func)
        result = cb.call(success_func)
        assert result == "ok"
