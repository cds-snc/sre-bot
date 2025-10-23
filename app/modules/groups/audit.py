# modules/groups/audit.py
from typing import Dict, Any
from datetime import datetime

from core.logging import get_module_logger
from integrations.sentinel import log_to_sentinel

logger = get_module_logger()


def log_group_action(payload: Dict[str, Any]) -> None:
    """Log group membership action to Sentinel for audit trail."""

    # Extract action type from the payload
    action_type = "unknown"
    if "member_email" in payload and "result" in payload:
        if "added" in str(payload.get("event_type", "")):
            action_type = "member_added"
        elif "removed" in str(payload.get("event_type", "")):
            action_type = "member_removed"

    audit_event = {
        "event_type": "group_membership_change",
        "action": action_type,
        "timestamp": datetime.utcnow().isoformat(),
        "group_id": payload.get("group_id"),
        "member_email": payload.get("member_email"),
        "requestor_email": payload.get("requestor_email"),
        "provider": payload.get("provider"),
        "justification": payload.get("justification"),
        "success": payload.get("result") is not None,
        "result_details": payload.get("result"),
    }

    # Log locally
    logger.info("group_membership_audit", **audit_event)

    # Send to Sentinel for external audit
    try:
        log_to_sentinel("group_membership_change", audit_event)
        logger.debug("Successfully logged group action to Sentinel")
    except (ConnectionError, TimeoutError, ValueError) as e:
        logger.error(f"Failed to log group action to Sentinel: {e}")


def get_audit_trail(group_id: str, limit: int = 50) -> list:
    """Get audit trail for a specific group (placeholder for future implementation)."""
    # For now, return empty list as placeholder
    logger.info(f"Retrieving audit trail for group {group_id} (limit: {limit})")
    return []


def get_user_audit_trail(user_email: str, limit: int = 50) -> list:
    """Get audit trail for a specific user's group actions (placeholder)."""
    logger.info(f"Retrieving audit trail for user {user_email} (limit: {limit})")
    return []
