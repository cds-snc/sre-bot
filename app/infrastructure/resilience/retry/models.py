"""Generic retry models.

This module defines the core data structures for the retry system.
These models are intentionally generic to support any module's retry needs.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class RetryResult(Enum):
    """Outcome of processing a retry record.

    Values:
        SUCCESS: Operation completed successfully, remove from queue
        RETRY: Operation failed but is retryable, schedule for retry
        PERMANENT_FAILURE: Operation failed permanently, move to DLQ
    """

    SUCCESS = "success"
    RETRY = "retry"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass
class RetryRecord:
    """Generic retry record for failed operations.

    This dataclass represents any operation that needs to be retried.
    Module-specific data is stored in the `payload` field.

    Fields:
        id: Unique identifier (assigned by store)
        operation_type: Namespace identifier (e.g., "groups.member.propagation")
        payload: Module-specific data (e.g., group_id, provider, action, etc.)
        attempts: Number of retry attempts
        last_error: Last error message encountered
        created_at: When the record was first created
        updated_at: When the record was last updated
        next_retry_at: Optional field for stores to track next retry time

    Example:
        # Groups module payload
        payload = {
            "group_id": "group-123",
            "provider": "google_workspace",
            "action": "add_member",
            "member_email": "user@example.com",
            "correlation_id": "abc-123"
        }

        record = RetryRecord(
            operation_type="groups.member.propagation",
            payload=payload
        )
    """

    # Generic fields
    operation_type: str
    payload: dict[str, Any]

    # Tracking fields
    id: str | None = None
    attempts: int = 0
    last_error: str | None = None

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Optional field for stores to manage retry scheduling
    next_retry_at: datetime | None = None

    def __post_init__(self) -> None:
        """Validate required fields."""
        if not self.operation_type:
            raise ValueError("operation_type is required")
        if not isinstance(self.payload, dict):
            raise ValueError("payload must be a dictionary")
