"""Circuit breaker implementation for provider resilience.

The circuit breaker pattern prevents cascading failures by:
1. CLOSED state: Normal operation, requests pass through
2. OPEN state: Fast-fail requests without calling provider (after threshold failures)
3. HALF_OPEN state: Test recovery with limited requests

State transitions:
- CLOSED -> OPEN: After failure_threshold consecutive failures
- OPEN -> HALF_OPEN: After timeout period expires
- HALF_OPEN -> CLOSED: After successful request
- HALF_OPEN -> OPEN: If request fails
"""

import threading
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Any, Optional, Dict

from core.logging import get_module_logger

logger = get_module_logger()


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests immediately
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""

    pass


class CircuitBreaker:
    """Circuit breaker for provider operations.

    Args:
        name: Name of the circuit (typically provider name)
        failure_threshold: Number of consecutive failures before opening
        timeout_seconds: Seconds to wait before attempting recovery (HALF_OPEN)
        half_open_max_calls: Max requests to allow in HALF_OPEN state
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.half_open_max_calls = half_open_max_calls

        # State management
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0

        # Thread safety
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by func
        """
        # Check if we should reject the request
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if timeout has elapsed
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    elapsed = (
                        datetime.utcnow() - self._last_failure_time
                    ).total_seconds()
                    remaining = self.timeout_seconds - elapsed
                    logger.warning(
                        "circuit_breaker_open",
                        name=self.name,
                        failure_count=self._failure_count,
                        retry_in_seconds=int(remaining),
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry in {int(remaining)} seconds."
                    )

            if self._state == CircuitState.HALF_OPEN:
                # Limit concurrent requests in HALF_OPEN state
                if self._half_open_calls >= self.half_open_max_calls:
                    logger.debug(
                        "circuit_breaker_half_open_limit",
                        name=self.name,
                        calls=self._half_open_calls,
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN "
                        f"(max concurrent calls reached)."
                    )
                self._half_open_calls += 1

        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
        finally:
            # Decrement half_open call counter
            with self._lock:
                if self._state == CircuitState.HALF_OPEN:
                    self._half_open_calls -= 1

    def _on_success(self):
        """Handle successful request."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    "circuit_breaker_success_half_open",
                    name=self.name,
                    success_count=self._success_count,
                )
                # Transition back to CLOSED after successful test
                self._transition_to_closed()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                if self._failure_count > 0:
                    logger.debug(
                        "circuit_breaker_failure_count_reset",
                        name=self.name,
                        previous_failures=self._failure_count,
                    )
                    self._failure_count = 0

    def _on_failure(self, exception: Exception):
        """Handle failed request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.utcnow()

            if self._state == CircuitState.HALF_OPEN:
                # Failed during recovery test, go back to OPEN
                logger.warning(
                    "circuit_breaker_recovery_failed",
                    name=self.name,
                    error=str(exception),
                )
                self._transition_to_open()
            elif self._state == CircuitState.CLOSED:
                # Check if we've hit the threshold
                if self._failure_count >= self.failure_threshold:
                    logger.error(
                        "circuit_breaker_threshold_exceeded",
                        name=self.name,
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold,
                        error=str(exception),
                    )
                    self._transition_to_open()
                else:
                    logger.warning(
                        "circuit_breaker_failure",
                        name=self.name,
                        failure_count=self._failure_count,
                        threshold=self.failure_threshold,
                        error=str(exception),
                    )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        elapsed = datetime.utcnow() - self._last_failure_time
        return elapsed >= timedelta(seconds=self.timeout_seconds)

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        logger.info("circuit_breaker_closed", name=self.name)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def _transition_to_open(self):
        """Transition to OPEN state."""
        logger.error(
            "circuit_breaker_opened",
            name=self.name,
            timeout_seconds=self.timeout_seconds,
        )
        self._state = CircuitState.OPEN
        self._half_open_calls = 0

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        logger.info("circuit_breaker_half_open", name=self.name)
        self._state = CircuitState.HALF_OPEN
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "last_failure_time": (
                    self._last_failure_time.isoformat()
                    if self._last_failure_time
                    else None
                ),
                "half_open_calls": self._half_open_calls,
            }

    def reset(self):
        """Manually reset circuit breaker (for testing/admin operations)."""
        with self._lock:
            logger.info("circuit_breaker_manual_reset", name=self.name)
            self._transition_to_closed()


# Global registry for monitoring
_circuit_breaker_registry: Dict[str, CircuitBreaker] = {}


def register_circuit_breaker(cb: CircuitBreaker) -> None:
    """Register a circuit breaker for monitoring."""
    _circuit_breaker_registry[cb.name] = cb


def get_all_circuit_breaker_stats() -> dict:
    """Get statistics for all circuit breakers."""
    return {name: cb.get_stats() for name, cb in _circuit_breaker_registry.items()}


def get_open_circuit_breakers() -> list:
    """Get list of circuit breakers that are currently OPEN."""
    return [
        name
        for name, cb in _circuit_breaker_registry.items()
        if cb.state == CircuitState.OPEN
    ]


def get_circuit_breaker(name: str) -> Optional[CircuitBreaker]:
    """Get a circuit breaker by name."""
    return _circuit_breaker_registry.get(name)
