"""Audit event models for SIEM integration.

This module defines the internal storage model for audit events:
- Type-safe (Pydantic validation)
- Minimal structure (supports any feature's payload)
- Rich optional metadata (via extra_metadata() from payload)
- Format-agnostic (output adapters handle SIEM specifics)

The AuditEvent accepts optional resource tracking (resource_type/resource_id)
to support features that don't have these concepts. All domain-specific fields
should be provided via extra_metadata() dict, which will be flattened with
the audit_meta_ prefix by output adapters (e.g., SentinelAdapter).
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditEvent(BaseModel):
    """Storage model for audit events.

    Designed to be:
    - Input-flexible: accepts minimal payloads from any feature
    - Schema-explicit: validates structure for storage consistency
    - Adapter-ready: provides all data needed by output adapters (Sentinel, etc.)

    The model itself is domain-neutral: it accepts whatever a feature provides.
    Output adapters (e.g., SentinelAdapter) handle format-specific serialization
    (flat structure, field prefixes, etc.).

    Attributes:
        correlation_id: Unique request ID for distributed tracing
            across services.
        timestamp: ISO 8601 timestamp when the event occurred (UTC).
        action: Operation type (e.g., 'member_added', 'group_created',
            'incident_resolved').
        user_email: Email of user who initiated the action.
        result: Overall operation result ('success' or 'failure').
        resource_type: Type of resource affected (e.g., 'group', 'incident', 'user').
            Optional if the feature doesn't have a resource concept.
        resource_id: Primary resource identifier (e.g., group email, incident ID).
            Optional if the feature doesn't have a resource concept.
        error_type: Category of error if failed (e.g., 'transient',
            'permanent', 'auth'). Only present if result == 'failure'.
        error_message: Human-readable error description if failed.
            Only present if result == 'failure'.
        provider: External system name (e.g., 'google', 'aws', 'slack').
            Only present if action involves external services.
        duration_ms: Operation duration in milliseconds if tracked. Optional
            metric for performance analysis.
        audit_meta_*: Any additional operation-specific fields from metadata,
            flattened with 'audit_meta_' prefix. Output adapters may further
            transform these (e.g., for SIEM queryability).
    """

    correlation_id: str = Field(..., description="Unique request ID for distributed tracing")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO 8601 timestamp (UTC)",
    )
    action: str = Field(..., description="Operation type (snake_case)")
    user_email: str = Field(..., description="User who initiated the action")
    result: str = Field(
        ...,
        description="Operation result: 'success' or 'failure'",
        pattern="^(success|failure)$",
    )
    resource_type: str | None = Field(default=None, description="Type of resource affected (optional)")
    resource_id: str | None = Field(default=None, description="Primary resource identifier (optional)")
    error_type: str | None = Field(
        default=None,
        description="Error category if failed: transient, permanent, auth, etc.",
    )
    error_message: str | None = Field(default=None, description="Human-readable error description")
    provider: str | None = Field(default=None, description="External system name")
    duration_ms: int | None = Field(default=None, description="Operation duration in milliseconds")

    model_config = ConfigDict(
        extra="allow",  # Allow audit_meta_* fields to be added dynamically
        json_schema_extra={
            "example": {
                "correlation_id": "req-abc123",
                "timestamp": "2025-01-08T12:00:00+00:00",
                "action": "member_added",
                "user_email": "alice@example.com",
                "resource_type": "group",
                "resource_id": "engineering@example.com",
                "result": "success",
                "provider": "google",
                "duration_ms": 500,
                "audit_meta_propagation_count": "2",
                "audit_meta_retry_count": "0",
            }
        },
    )

    def to_sentinel_payload(self) -> dict[str, Any]:
        """Convert to flat dict suitable for SIEM ingestion.

        Returns:
            Dictionary with all model fields included (excluding None values).
            Output adapters (e.g., SentinelAdapter) may further transform this
            into SIEM-specific formats.
        """
        return dict(self.model_dump(exclude_none=True))

    @classmethod
    def from_metadata(
        cls,
        correlation_id: str,
        action: str,
        user_email: str,
        result: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
        provider: str | None = None,
        duration_ms: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        """Construct an AuditEvent from primitive operation metadata.

        Flattens the optional ``metadata`` dict into top-level fields with the
        ``audit_meta_`` prefix. All metadata values are coerced to strings for
        SIEM compatibility. Output adapters may handle these fields according
        to their specific format requirements.

        Args:
            correlation_id: Unique request ID for distributed tracing.
            action: Operation type in snake_case (e.g., 'member_added').
            user_email: Email of user who initiated the action.
            result: Operation result — must be ``'success'`` or ``'failure'``.
            resource_type: Type of resource affected (optional). Omit if the
                feature doesn't track resources (e.g., infra events).
            resource_id: Primary resource identifier (optional). Omit if the
                feature doesn't track resources.
            error_type: Error category if failed (transient/permanent/auth/etc).
            error_message: Human-readable error description if failed.
            provider: External system name if applicable (google/aws/slack/etc).
            duration_ms: Operation duration in milliseconds if tracked.
            metadata: Additional operation-specific data to flatten with the
                ``audit_meta_`` prefix (e.g., {"retry_count": 3} becomes
                audit_meta_retry_count in the event).

        Returns:
            AuditEvent instance ready for storage.

        Raises:
            ValueError: If ``result`` is not ``'success'`` or ``'failure'``.
        """
        if result not in ("success", "failure"):
            raise ValueError(f"result must be 'success' or 'failure', got: {result}")

        event_data: dict[str, Any] = {
            "correlation_id": correlation_id,
            "action": action,
            "user_email": user_email,
            "result": result,
        }

        if resource_type is not None:
            event_data["resource_type"] = resource_type
        if resource_id is not None:
            event_data["resource_id"] = resource_id
        if error_type is not None:
            event_data["error_type"] = error_type
        if error_message is not None:
            event_data["error_message"] = error_message
        if provider is not None:
            event_data["provider"] = provider
        if duration_ms is not None:
            event_data["duration_ms"] = duration_ms

        # Flatten metadata with 'audit_meta_' prefix for SIEM queryability
        if metadata:
            for key, value in metadata.items():
                event_data[f"audit_meta_{key}"] = str(value) if value is not None else None

        return cls(**event_data)
