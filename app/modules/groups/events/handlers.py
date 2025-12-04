"""Groups membership event consumers.

This module contains only passive, post-write consumers (audit and
notifications) that subscribe to canonical events emitted by the service
boundary. All write operations (adds/removes) are performed by the
`service` layer.
"""

from infrastructure.events import register_event_handler, Event
from core.logging import get_module_logger
from modules.groups.infrastructure import audit
from modules.groups.infrastructure import notifications

logger = get_module_logger()


def _log_group_action_to_audit(payload: Event) -> None:
    """Log group action to audit trail for compliance.

    Expects the canonical nested event payload produced by the service.
    Converts event payload into AuditEntry for structured logging.
    """
    # Extract metadata which contains request and orchestration details
    event_dict = payload.to_dict()
    metadata = event_dict.get("metadata", {})
    req = metadata.get("request") or {}
    orch = metadata.get("orchestration") or {}

    # Determine action type from orchestration details
    action_type = orch.get("action", "unknown")

    # Handle different operation types - list operations don't have a single group_id
    group_id = req.get("group_id") or orch.get("group_id", "")
    if not group_id and action_type == "list_groups":
        # For list operations, use a descriptive identifier
        group_id = f"list_operation_{orch.get('group_count', 0)}_groups"

    # Create audit entry from event payload
    audit_entry = audit.create_audit_entry_from_operation(
        correlation_id=orch.get("correlation_id", ""),
        action=action_type,
        group_id=group_id,
        provider=req.get("provider") or orch.get("provider", "unknown"),
        success=bool(orch.get("success", False)),
        requestor=req.get("requestor"),
        member_email=req.get("member_email") or orch.get("member_email"),
        justification=req.get("justification"),
        metadata=orch,
    )

    # Write to audit trail (synchronous)
    audit.write_audit_entry(audit_entry)


@register_event_handler("group.member.added")
def handle_member_added(payload: Event) -> None:
    """Handle post-addition tasks (audit + notifications).

    Expects the canonical nested event payload produced by the service, e.g.
    {"orchestration": {...}, "request": {...}}
    """

    # Log to audit trail
    _log_group_action_to_audit(payload)

    # Send notifications
    notifications.send_group_notifications(payload)


@register_event_handler("group.member.removed")
def handle_member_removed(payload: Event) -> None:
    """Handle post-removal tasks (audit + notifications)."""

    # Log to audit trail
    _log_group_action_to_audit(payload)

    # Send notifications
    notifications.send_group_notifications(payload)


@register_event_handler("group.listed")
def handle_group_listed(payload: Event) -> None:
    """Handle post-listing tasks (audit)."""

    # Log to audit trail
    _log_group_action_to_audit(payload)

    # Send notifications
    notifications.send_group_notifications(payload)
