"""Sentinel SIEM adapter for audit events.

Converts internal AuditEvent records into flat format required by Sentinel.
All metadata fields are stringified and prefixed with 'audit_meta_' for
queryability in Sentinel's query language.
"""

from typing import Any

from infrastructure.audit.models import AuditEvent


class SentinelAdapter:
    """Adapter for serializing audit events to Sentinel SIEM format.

    Sentinel requires:
    - Flat (non-nested) field structure for querying
    - All values stringifiable (numbers, booleans, etc. must be convertible)
    - Optional metadata fields prefixed for organization and queryability

    This adapter handles the transformation from the internal AuditEvent model
    to Sentinel's wire format. As the only output adapter in use, it may be
    called directly. When additional adapters are needed (CloudTrail, DataDog),
    this pattern allows adding them without changing the service interface.
    """

    @staticmethod
    def to_sentinel_format(audit_event: AuditEvent) -> dict[str, Any]:
        """Convert AuditEvent to flat Sentinel format for SIEM ingestion.

        Args:
            audit_event: Internal audit event record.

        Returns:
            Flat dict with all fields stringified, ready for Sentinel ingestion.
            Includes all audit_meta_* prefixed fields from event metadata.

        Example:
            >>> event = AuditEvent(
            ...     correlation_id="req-123",
            ...     action="member_added",
            ...     user_email="alice@example.com",
            ...     result="success",
            ...     audit_meta_resource_type="group",      # from metadata
            ...     audit_meta_resource_id="eng@example.com" # from metadata
            ... )
            >>> payload = SentinelAdapter.to_sentinel_format(event)
            >>> # Returns flat dict with all fields, no nesting
        """
        payload = audit_event.to_sentinel_payload()

        # Ensure consistency: stringify all values for SIEM compatibility
        # (Sentinel query language works best with consistent string types)
        result: dict[str, Any] = {}
        for key, value in payload.items():
            if value is None:
                continue
            # Already stringified by to_sentinel_payload, but ensure consistency
            result[key] = value

        return result
