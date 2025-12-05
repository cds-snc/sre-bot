"""Audit event models for SIEM integration.

This module defines structured audit events that are:
- Type-safe (Pydantic validation)
- Flat structure (easy Sentinel queries)
- Compliant (all required audit fields)
- Reusable (not feature-specific)
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class AuditEvent(BaseModel):
    """Structured audit event for SIEM integration.

    Uses a flat field structure to maximize queryability in Sentinel and other
    SIEM tools. All field names are prefixed to avoid collision with Sentinel
    reserved words.

    Attributes:
        correlation_id: Unique request ID for distributed tracing
            across services.
        timestamp: ISO 8601 timestamp when the event occurred (UTC).
        action: Operation type (e.g., 'member_added', 'group_created',
            'incident_resolved').
        resource_type: Type of resource affected (e.g., 'group', 'incident', 'user').
        resource_id: Primary resource identifier (e.g., group email, incident ID).
        user_email: Email of user who initiated the action.
        result: Overall operation result ('success' or 'failure').
        error_type: Category of error if failed (e.g., 'transient',
            'permanent', 'auth'). Only present if result == 'failure'.
        error_message: Human-readable error description if failed.
            Only present if result == 'failure'.
        provider: External system name (e.g., 'google', 'aws', 'slack').
            Only present if action involves external services.
        duration_ms: Operation duration in milliseconds if tracked. Optional
            metric for performance analysis.
        metadata_keys: Comma-separated list of metadata field names for auditing.
            Flattened metadata fields (e.g., 'member_count', 'retry_count') are
            prefixed with 'audit_meta_' and included at top level.
        audit_meta_*: Any additional operation-specific fields from metadata,
            flattened with 'audit_meta_' prefix to avoid name collisions.
    """

    correlation_id: str = Field(
        ..., description="Unique request ID for distributed tracing"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 timestamp (UTC)",
    )
    action: str = Field(..., description="Operation type (snake_case)")
    resource_type: str = Field(..., description="Type of resource affected")
    resource_id: str = Field(..., description="Primary resource identifier")
    user_email: str = Field(..., description="User who initiated the action")
    result: str = Field(
        ...,
        description="Operation result: 'success' or 'failure'",
        pattern="^(success|failure)$",
    )
    error_type: Optional[str] = Field(
        default=None,
        description="Error category if failed: transient, permanent, auth, etc.",
    )
    error_message: Optional[str] = Field(
        default=None, description="Human-readable error description"
    )
    provider: Optional[str] = Field(default=None, description="External system name")
    duration_ms: Optional[int] = Field(
        default=None, description="Operation duration in milliseconds"
    )

    model_config = ConfigDict(
        extra="allow",  # Allow audit_meta_* fields to be added dynamically
        json_schema_extra={
            "example": {
                "correlation_id": "req-abc123",
                "timestamp": "2025-01-08T12:00:00+00:00",
                "action": "member_added",
                "resource_type": "group",
                "resource_id": "engineering@example.com",
                "user_email": "alice@example.com",
                "result": "success",
                "provider": "google",
                "duration_ms": 500,
                "audit_meta_propagation_count": "2",
                "audit_meta_retry_count": "0",
            }
        },
    )

    def to_sentinel_payload(self) -> Dict[str, Any]:
        """Convert to flat Sentinel payload for SIEM ingestion.

        Returns:
            Dictionary with flat structure suitable for Sentinel logging.
            All model_dump() fields are included directly (no nesting).
        """
        return self.model_dump(exclude_none=True)


def create_audit_event(
    correlation_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    user_email: str,
    result: str,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    provider: Optional[str] = None,
    duration_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """Factory function to create audit events.

    Converts operation metadata into flattened audit fields with 'audit_meta_'
    prefix to maintain flat structure for Sentinel queryability.

    Args:
        correlation_id: Unique request ID for distributed tracing.
        action: Operation type (snake_case, e.g., 'member_added').
        resource_type: Type of resource affected (e.g., 'group', 'incident').
        resource_id: Primary resource identifier (email, ID, etc.).
        user_email: Email of user who initiated the action.
        result: Operation result ('success' or 'failure').
        error_type: Category of error if failed (transient/permanent/auth/etc).
        error_message: Human-readable error description if failed.
        provider: External system name if applicable (google/aws/slack/etc).
        duration_ms: Operation duration in milliseconds if tracked.
        metadata: Additional operation-specific data to flatten with
            'audit_meta_' prefix.

    Returns:
        AuditEvent instance ready for Sentinel logging.

    Raises:
        ValueError: If result is not 'success' or 'failure'.
    """
    if result not in ("success", "failure"):
        raise ValueError(f"result must be 'success' or 'failure', got: {result}")

    # Create base event with all fields
    event_data: Dict[str, Any] = {
        "correlation_id": correlation_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "user_email": user_email,
        "result": result,
    }

    # Add optional fields
    if error_type is not None:
        event_data["error_type"] = error_type
    if error_message is not None:
        event_data["error_message"] = error_message
    if provider is not None:
        event_data["provider"] = provider
    if duration_ms is not None:
        event_data["duration_ms"] = duration_ms

    # Flatten metadata with 'audit_meta_' prefix
    if metadata:
        for key, value in metadata.items():
            # Convert non-string values to strings for Sentinel compatibility
            meta_key = f"audit_meta_{key}"
            event_data[meta_key] = str(value) if value is not None else None

    return AuditEvent(**event_data)
