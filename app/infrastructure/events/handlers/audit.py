"""Audit handler for event system.

Converts events to structured audit events and writes to Sentinel for compliance
and DynamoDB for operational queries.
"""

from typing import Optional, Dict, Any

from core.logging import get_module_logger
from infrastructure.audit.models import create_audit_event
from infrastructure.events.models import Event
from infrastructure.persistence import dynamodb_audit
from integrations.sentinel import client as sentinel_client

logger = get_module_logger()


def _extract_resource_info(
    event_type: str, metadata: Dict[str, Any]
) -> tuple[Optional[str], Optional[str]]:
    """Extract resource_type and resource_id from event metadata.

    Args:
        event_type: The event type (e.g., 'group.member.added').
        metadata: Event metadata dictionary.

    Returns:
        Tuple of (resource_type, resource_id) or (None, None) if not found.
    """
    # Map event types to resource extraction logic
    if event_type.startswith("group."):
        resource_type = "group"
        resource_id = metadata.get("group_id") or metadata.get("group_email")
        return resource_type, resource_id

    if event_type.startswith("incident."):
        resource_type = "incident"
        resource_id = metadata.get("incident_id")
        return resource_type, resource_id

    if event_type.startswith("webhook."):
        resource_type = "webhook"
        resource_id = metadata.get("webhook_id")
        return resource_type, resource_id

    # Generic fallback
    resource_type_fallback: Optional[str] = metadata.get("resource_type")
    resource_id_fallback: Optional[str] = metadata.get("resource_id")
    return resource_type_fallback, resource_id_fallback


def _extract_provider(metadata: Dict[str, Any]) -> Optional[str]:
    """Extract provider from event metadata.

    Args:
        metadata: Event metadata dictionary.

    Returns:
        Provider name (e.g., 'google', 'aws', 'slack') or None.
    """
    # Check common metadata locations
    provider = metadata.get("provider")
    if provider:
        return provider

    # Infer from orchestration result if present
    orch = metadata.get("orchestration")
    if orch and isinstance(orch, dict):
        return orch.get("provider")

    # Infer from request if present
    request = metadata.get("request")
    if request and isinstance(request, dict):
        return request.get("provider")

    return None


def _extract_justification(metadata: Dict[str, Any]) -> Optional[str]:
    """Extract justification from event metadata.

    Justification can be in multiple locations depending on the event type:
    - Directly in metadata (legacy)
    - In nested request dict (modern, from service layer)
    - In nested orchestration result

    Args:
        metadata: Event metadata dictionary.

    Returns:
        Justification string or None.
    """
    # Check direct metadata first
    justification = metadata.get("justification")
    if justification:
        return justification

    # Check nested in request (from service layer)
    request = metadata.get("request")
    if request and isinstance(request, dict):
        justification = request.get("justification")
        if justification:
            return justification

    # Check nested in orchestration result
    orch = metadata.get("orchestration")
    if orch and isinstance(orch, dict):
        justification = orch.get("justification")
        if justification:
            return justification

    return None


def _is_success(metadata: Dict[str, Any]) -> bool:
    """Determine if event represents success or failure.

    Args:
        metadata: Event metadata dictionary.

    Returns:
        True if success, False if failure.
    """
    # Check explicit success/failure indicators
    if "success" in metadata:
        return metadata.get("success", True)

    if "result" in metadata:
        result = metadata.get("result")
        return result == "success" if isinstance(result, str) else bool(result)

    # Infer from orchestration result
    orch = metadata.get("orchestration")
    if orch and isinstance(orch, dict):
        return orch.get("success", True)

    # Default to success if no failure indicators
    return True


class AuditHandler:
    """Handles audit trail writing for events.

    Converts infrastructure events to structured audit events and writes them
    to Sentinel for compliance and audit trail purposes.
    """

    def __init__(self, sentinel_client_override=None):
        """Initialize audit handler.

        Args:
            sentinel_client_override: Override sentinel client (for testing).
        """
        self.sentinel_client = sentinel_client_override or sentinel_client

    def handle(self, event: Event) -> None:
        """Handle event by converting to audit event and writing to Sentinel.

        This handler is resilient and never raises exceptions. If audit logging
        fails, the error is logged but the system continues operating.

        Args:
            event: The event to audit.
        """
        try:
            logger.info(
                "converting_event_to_audit",
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
            )

            # Extract structured fields from event
            resource_type, resource_id = _extract_resource_info(
                event.event_type, event.metadata
            )
            provider = _extract_provider(event.metadata)
            justification = _extract_justification(event.metadata)
            success = _is_success(event.metadata)

            # Determine result and error fields
            result = "success" if success else "failure"
            error_type = None
            error_message = None

            if not success:
                error_type = event.metadata.get("error_type", "unknown")
                error_message = event.metadata.get("error_message", "Operation failed")

            # Filter metadata to exclude structural fields and fields used for resource extraction
            filtered_metadata = {
                k: v
                for k, v in event.metadata.items()
                if k
                not in {
                    "success",
                    "result",
                    "error_type",
                    "error_message",
                    "provider",
                    "resource_type",
                    "resource_id",
                    "group_id",
                    "group_email",
                    "incident_id",
                    "webhook_id",
                    "justification",  # Extracted separately and added below
                }
            }

            # Add justification if present (for audit compliance)
            if justification:
                filtered_metadata["justification"] = justification

            # Create audit event
            audit_event = create_audit_event(
                correlation_id=str(event.correlation_id),
                action=event.event_type.replace(".", "_"),
                resource_type=resource_type or "unknown",
                resource_id=resource_id or "unknown",
                user_email=event.user_email or "system",
                result=result,
                error_type=error_type,
                error_message=error_message,
                provider=provider,
                metadata=filtered_metadata if filtered_metadata else None,
            )

            # Log audit event to Sentinel
            self.sentinel_client.log_audit_event(audit_event)

            # Also write to DynamoDB for operational queries (non-blocking)
            dynamodb_audit.write_audit_event(audit_event)

            logger.info(
                "audit_event_written",
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
                action=audit_event.action,
                resource_type=audit_event.resource_type,
            )

        except Exception as e:
            # Never fail - log error and continue
            logger.error(
                "failed_to_write_audit_event",
                event_type=event.event_type,
                correlation_id=str(event.correlation_id),
                error=str(e),
                error_type=type(e).__name__,
            )


def handle_audit_event(event: Event) -> None:
    """Handler function for audit events.

    This is registered as a handler for all event types to ensure
    all system events are logged to Sentinel for compliance.

    Args:
        event: The event to audit.
    """
    handler = AuditHandler()
    handler.handle(event)
