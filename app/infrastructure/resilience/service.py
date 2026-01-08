"""Resilience service for dependency injection.

Provides a class-based interface to circuit breakers and retry stores for easier DI and testing.
"""

from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

import structlog
from infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)

if TYPE_CHECKING:
    from infrastructure.resilience.retry.config import RetryConfig
    from infrastructure.resilience.retry.store import RetryStore
    from infrastructure.configuration import Settings

logger = structlog.get_logger()


class ResilienceService:
    """Class-based resilience service.

    Provides unified access to circuit breakers and retry stores through
    a service interface that supports dependency injection and testing.

    This service:
    - Manages a registry of circuit breakers
    - Provides access to retry store functionality
    - Offers helper methods for common resilience patterns

    Usage:
        # Via dependency injection
        from infrastructure.services import ResilienceServiceDep

        @router.get("/external-call")
        def make_external_call(resilience: ResilienceServiceDep):
            cb = resilience.get_or_create_circuit_breaker(
                "external_api",
                failure_threshold=5
            )
            try:
                result = cb.call(external_api_function)
                return result
            except CircuitBreakerOpenError:
                return {"error": "Service temporarily unavailable"}

        # Direct instantiation
        from infrastructure.resilience import ResilienceService

        service = ResilienceService()
        breaker = service.create_circuit_breaker("my_service")
    """

    def __init__(
        self,
        settings: "Settings",
        retry_store: Optional["RetryStore"] = None,
        retry_config: Optional["RetryConfig"] = None,
    ):
        """Initialize resilience service.

        Args:
            settings: Settings instance (required, passed from provider).
            retry_store: Optional pre-configured RetryStore instance.
                        If not provided, creates from factory using settings.
            retry_config: Optional RetryConfig for creating retry store.
                         Used only if retry_store is None.
        """
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        if retry_store is not None:
            self._retry_store = retry_store
        else:
            # Import here to avoid circular dependency
            from infrastructure.resilience.retry.config import RetryConfig
            from infrastructure.resilience.retry.factory import create_retry_store

            config = retry_config or RetryConfig()
            self._retry_store = create_retry_store(config, settings)

    def create_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3,
    ) -> CircuitBreaker:
        """Create and register a new circuit breaker.

        Args:
            name: Unique name for the circuit breaker
            failure_threshold: Number of consecutive failures before opening
            timeout_seconds: Seconds to wait before attempting recovery
            half_open_max_calls: Max requests to allow in HALF_OPEN state

        Returns:
            CircuitBreaker instance

        Raises:
            ValueError: If circuit breaker with this name already exists
        """
        if name in self._circuit_breakers:
            raise ValueError(f"Circuit breaker '{name}' already exists")

        cb = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
            half_open_max_calls=half_open_max_calls,
        )
        self._circuit_breakers[name] = cb

        logger.info(
            "circuit_breaker_created",
            name=name,
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
        )

        return cb

    def get_circuit_breaker(self, name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker by name.

        Args:
            name: Circuit breaker name

        Returns:
            CircuitBreaker instance or None if not found
        """
        return self._circuit_breakers.get(name)

    def get_or_create_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        half_open_max_calls: int = 3,
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create if not found.

        Args:
            name: Circuit breaker name
            failure_threshold: Used only if creating new breaker
            timeout_seconds: Used only if creating new breaker
            half_open_max_calls: Used only if creating new breaker

        Returns:
            CircuitBreaker instance
        """
        existing = self.get_circuit_breaker(name)
        if existing:
            return existing

        return self.create_circuit_breaker(
            name=name,
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
            half_open_max_calls=half_open_max_calls,
        )

    def call_with_circuit_breaker(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Execute function through circuit breaker.

        Convenience method that gets or creates circuit breaker and executes function.

        Args:
            name: Circuit breaker name
            func: Function to call
            *args, **kwargs: Arguments to pass to function

        Returns:
            Result from function

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception raised by func
        """
        cb = self.get_or_create_circuit_breaker(name)
        return cb.call(func, *args, **kwargs)

    def get_all_circuit_breaker_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all registered circuit breakers.

        Returns:
            Dict mapping circuit breaker name to stats dict
        """
        return {name: cb.get_stats() for name, cb in self._circuit_breakers.items()}

    def get_open_circuit_breakers(self) -> list[str]:
        """Get list of circuit breakers that are currently OPEN.

        Returns:
            List of circuit breaker names in OPEN state
        """
        return [
            name
            for name, cb in self._circuit_breakers.items()
            if cb.state == CircuitState.OPEN
        ]

    def reset_circuit_breaker(self, name: str) -> None:
        """Manually reset a circuit breaker.

        Args:
            name: Circuit breaker name

        Raises:
            KeyError: If circuit breaker not found
        """
        cb = self._circuit_breakers.get(name)
        if not cb:
            raise KeyError(f"Circuit breaker '{name}' not found")

        cb.reset()

    @property
    def retry_store(self) -> "RetryStore":
        """Access underlying RetryStore instance.

        Provided for retry operations and worker integration.

        Returns:
            The underlying RetryStore instance
        """
        return self._retry_store

    def list_circuit_breakers(self) -> list[str]:
        """List all registered circuit breaker names.

        Returns:
            List of circuit breaker names
        """
        return list(self._circuit_breakers.keys())
