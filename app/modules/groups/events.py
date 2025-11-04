"""Groups membership event consumers.

This module contains only passive, post-write consumers (audit and
notifications) that subscribe to canonical events emitted by the service
boundary. All write operations (adds/removes) are performed by the
`service` layer; legacy handlers that invoked `base` helpers have been
removed to enforce the new architecture.
"""

from typing import Dict, Any

from modules.groups.event_system import register_event_handler
from core.logging import get_module_logger
from modules.groups import audit
from modules.groups.notifications import send_group_notifications

logger = get_module_logger()


def _log_group_action_to_audit(payload: Dict[str, Any]) -> None:
    """Log group action to audit trail for compliance.

    Expects the canonical nested event payload produced by the service.
    Converts event payload into AuditEntry for structured logging.
    """
    # Extract request and orchestration details from payload
    req = payload.get("request") or {}
    orch = payload.get("orchestration") or {}

    # Determine action type from orchestration details
    action_type = orch.get("action", "unknown")

    # Create audit entry from event payload
    audit_entry = audit.create_audit_entry_from_operation(
        correlation_id=orch.get("correlation_id", ""),
        action=action_type,
        group_id=req.get("group_id") or orch.get("group_id", ""),
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
def handle_member_added(payload: Dict[str, Any]) -> None:
    """Handle post-addition tasks (audit + notifications).

    Expects the canonical nested event payload produced by the service, e.g.
    {"orchestration": {...}, "request": {...}}
    """

    # Log to audit trail
    _log_group_action_to_audit(payload)

    # Send notifications
    send_group_notifications(payload)


@register_event_handler("group.member.removed")
def handle_member_removed(payload: Dict[str, Any]) -> None:
    """Handle post-removal tasks (audit + notifications)."""

    # Log to audit trail
    _log_group_action_to_audit(payload)

    # Send notifications
    send_group_notifications(payload)
