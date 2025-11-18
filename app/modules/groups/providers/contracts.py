"""Provider contracts: Pure dataclasses defining operation results and metadata.

This module contains only data structures (no business logic) that define
the contract between providers and orchestration layers. These are used as
return envelopes and metadata containers.

Key distinction:
  - contracts.py: Pure DTOs and enums for operation results and metadata
  - base.py: Abstract classes and lifecycle management
  - models.py: Domain entities (NormalizedMember, NormalizedGroup)
  - schemas.py: API validation (Pydantic models)
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass


class OperationStatus(Enum):
    """Status codes for provider operation results."""

    SUCCESS = "success"
    TRANSIENT_ERROR = "transient_error"  # Retryable
    PERMANENT_ERROR = "permanent_error"  # Do not retry
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"


@dataclass
class OperationResult:
    """Uniform result returned from provider operations.

    Attributes:
        status: OperationStatus -- high-level outcome
        message: str -- human-friendly message (for logs/troubleshooting)
        data: Optional[Dict[str, Any]] -- optional payload
        error_code: Optional[str] -- optional machine error code
        retry_after: Optional[int] -- seconds until retry when rate-limited
    """

    status: OperationStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    retry_after: Optional[int] = None  # Seconds for rate limiting

    @classmethod
    def success(
        cls, data: Optional[Dict[str, Any]] = None, message: str = "ok"
    ) -> "OperationResult":
        """Create a SUCCESS OperationResult with optional data."""
        return cls(status=OperationStatus.SUCCESS, message=message, data=data)

    @classmethod
    def error(
        cls,
        status: OperationStatus,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
    ) -> "OperationResult":
        """Create an error OperationResult with status, message, and optional metadata."""
        return cls(
            status=status,
            message=message,
            error_code=error_code,
            retry_after=retry_after,
        )

    @classmethod
    def transient_error(
        cls,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
    ) -> "OperationResult":
        """Create a transient (retryable) error result."""
        return cls.error(
            OperationStatus.TRANSIENT_ERROR, message, error_code, retry_after
        )

    @classmethod
    def permanent_error(
        cls, message: str, error_code: Optional[str] = None
    ) -> "OperationResult":
        """Create a permanent (non-retryable) error result."""
        return cls.error(OperationStatus.PERMANENT_ERROR, message, error_code)


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
