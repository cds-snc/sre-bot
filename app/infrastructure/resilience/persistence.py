"""Circuit breaker state persistence using AWS ElastiCache.

Provides persistent storage for circuit breaker states across application
restarts and distributed deployments. Uses ElastiCache (Redis/Valkey) as
the backing store.

Features:
- Shared state across ECS instances
- Survives application restarts
- Automatic TTL management
- Fallback to in-memory if ElastiCache unavailable

Usage:
    from infrastructure.resilience.persistence import CircuitBreakerStateStore
    from integrations.aws.elasticache import get_elasticache_client

    # Initialize with ElastiCache
    store = CircuitBreakerStateStore()

    # Use with circuit breaker
    cb = CircuitBreaker(
        name="google_workspace",
        state_store=store
    )
"""

from typing import Optional
from datetime import datetime
import json

from core.config import settings
from core.logging import get_module_logger
from integrations.aws.elasticache import (
    get_value,
    set_value,
    delete_value,
    exists,
)

logger = get_module_logger()


class CircuitBreakerStateStore:
    """Persist circuit breaker state to ElastiCache (Redis/Valkey).

    Stores circuit breaker state with automatic TTL to prevent stale state
    from persisting indefinitely. Falls back to no-op if ElastiCache is
    disabled or unavailable.

    Args:
        key_prefix: Prefix for all keys (default: "circuit_breaker")
        default_ttl_seconds: Default TTL for state storage (default: 3600)
    """

    def __init__(
        self,
        key_prefix: str = "circuit_breaker",
        default_ttl_seconds: int = 3600,
    ):
        self.key_prefix = key_prefix
        self.default_ttl_seconds = default_ttl_seconds
        self.enabled = settings.elasticache.ELASTICACHE_ENABLED

        if not self.enabled:
            logger.info(
                "circuit_breaker_persistence_disabled",
                reason="ELASTICACHE_ENABLED=False",
            )

    def _make_key(self, name: str) -> str:
        """Generate Redis key for circuit breaker."""
        return f"{self.key_prefix}:{name}"

    def save_state(self, name: str, state: dict) -> None:
        """Save circuit breaker state to ElastiCache.

        Args:
            name: Circuit breaker name
            state: State dictionary to persist
        """
        if not self.enabled:
            return

        key = self._make_key(name)

        # Add metadata
        state_with_metadata = {
            **state,
            "updated_at": datetime.utcnow().isoformat(),
        }

        result = set_value(
            key,
            state_with_metadata,
            ttl_seconds=self.default_ttl_seconds,
        )

        if result.is_success:
            logger.debug(
                "circuit_breaker_state_saved",
                name=name,
                state=state.get("state"),
                ttl_seconds=self.default_ttl_seconds,
            )
        else:
            logger.warning(
                "circuit_breaker_state_save_failed",
                name=name,
                error=result.message,
                error_code=result.error_code,
            )

    def load_state(self, name: str) -> Optional[dict]:
        """Load circuit breaker state from ElastiCache.

        Args:
            name: Circuit breaker name

        Returns:
            State dictionary if found, None otherwise
        """
        if not self.enabled:
            return None

        key = self._make_key(name)

        result = get_value(key, deserialize_json=True)

        if result.is_success and result.data:
            logger.debug(
                "circuit_breaker_state_loaded",
                name=name,
                state=result.data.get("state"),
            )
            return result.data
        elif result.is_success:
            logger.debug(
                "circuit_breaker_state_not_found",
                name=name,
            )
            return None
        else:
            logger.warning(
                "circuit_breaker_state_load_failed",
                name=name,
                error=result.message,
                error_code=result.error_code,
            )
            return None

    def delete_state(self, name: str) -> None:
        """Delete circuit breaker state from ElastiCache.

        Args:
            name: Circuit breaker name
        """
        if not self.enabled:
            return

        key = self._make_key(name)

        result = delete_value(key)

        if result.is_success:
            logger.debug(
                "circuit_breaker_state_deleted",
                name=name,
            )
        else:
            logger.warning(
                "circuit_breaker_state_delete_failed",
                name=name,
                error=result.message,
            )

    def exists_state(self, name: str) -> bool:
        """Check if circuit breaker state exists in ElastiCache.

        Args:
            name: Circuit breaker name

        Returns:
            True if state exists, False otherwise
        """
        if not self.enabled:
            return False

        key = self._make_key(name)

        result = exists(key)

        if result.is_success:
            return bool(result.data)
        else:
            logger.warning(
                "circuit_breaker_state_exists_check_failed",
                name=name,
                error=result.message,
            )
            return False
