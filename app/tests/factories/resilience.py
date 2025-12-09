"""Factory functions for ElastiCache and resilience test data."""

from typing import Dict, Any, Optional


def make_circuit_breaker_state(
    state: str = "CLOSED",
    failure_count: int = 0,
    success_count: int = 0,
    last_failure_time: Optional[str] = None,
    updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Create circuit breaker state dictionary.

    Args:
        state: Circuit breaker state (CLOSED, OPEN, HALF_OPEN)
        failure_count: Number of consecutive failures
        success_count: Number of consecutive successes
        last_failure_time: ISO format timestamp of last failure
        updated_at: ISO format timestamp of last update

    Returns:
        Dictionary with circuit breaker state data
    """
    state_data = {
        "state": state,
        "failure_count": failure_count,
        "success_count": success_count,
    }

    if last_failure_time:
        state_data["last_failure_time"] = last_failure_time

    if updated_at:
        state_data["updated_at"] = updated_at

    return state_data


def make_elasticache_key(name: str, prefix: str = "circuit_breaker") -> str:
    """Create ElastiCache key for circuit breaker.

    Args:
        name: Circuit breaker name
        prefix: Key prefix

    Returns:
        Full Redis key string
    """
    return f"{prefix}:{name}"
