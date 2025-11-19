"""Provider contracts: Pure dataclasses defining operation results and metadata.

This module contains only data structures (no business logic) that define
the contract between providers and orchestration layers. These are used as
return envelopes and metadata containers.

Key distinction:
  - infrastructure/operations: Application-wide OperationResult and OperationStatus
  - contracts.py: Provider-specific contracts (HealthCheckResult, CircuitBreakerStats, ProviderCapabilities)
  - base.py: Abstract classes and lifecycle management
  - models.py: Domain entities (NormalizedMember, NormalizedGroup)
  - schemas.py: API validation (Pydantic models)
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from dataclasses import dataclass

# Import from infrastructure - single source of truth for OperationResult/OperationStatus
from infrastructure.operations import OperationResult, OperationStatus

__all__ = [
    "OperationResult",
    "OperationStatus",
    "HealthCheckResult",
    "CircuitBreakerStats",
    "ProviderCapabilities",
]


@dataclass
class HealthCheckResult:
    """Result of a provider health check operation.

    Attributes:
        healthy: Whether the provider is healthy and operational
        status: Human-readable status ("healthy", "unhealthy", "degraded")
        details: Optional provider-specific details about the health state
        timestamp: Optional ISO 8601 timestamp of the check
    """

    healthy: bool
    status: str  # "healthy", "unhealthy", "degraded"
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


@dataclass
class CircuitBreakerStats:
    """Statistics and state information for a circuit breaker.

    Attributes:
        enabled: Whether the circuit breaker is enabled for this provider
        state: Current state ("CLOSED", "OPEN", "HALF_OPEN")
        failure_count: Number of consecutive failures
        success_count: Number of consecutive successes
        last_failure_time: Timestamp of the last failure, or None
        message: Optional human-readable message about the circuit state
    """

    enabled: bool
    state: str  # "CLOSED", "OPEN", "HALF_OPEN"
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    message: Optional[str] = None


@dataclass
class ProviderCapabilities:
    """Capability flags for a provider.

    Pure data structure (no config access). Use capabilities.load_capabilities()
    to load from settings with overrides applied.

    Attributes:
        supports_user_creation: Provider can create users
        supports_user_deletion: Provider can delete users
        supports_group_creation: Should always be False
        supports_group_deletion: Should always be False
        supports_member_management: Provider can add/remove members
        is_primary: Provider is the authoritative source of truth
        provides_role_info: Provider returns role information for members
        supports_batch_operations: Provider supports batch operations
        max_batch_size: Maximum batch size for operations (if supported)
    """

    supports_user_creation: bool = False
    supports_user_deletion: bool = False
    supports_group_creation: bool = False  # Should always be False
    supports_group_deletion: bool = False  # Should always be False
    supports_member_management: bool = True
    is_primary: bool = False
    provides_role_info: bool = False
    supports_batch_operations: bool = False
    max_batch_size: int = 1
