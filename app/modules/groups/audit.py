# modules/groups/audit.py
from typing import Dict, Any
from datetime import datetime

from core.logging import get_module_logger
from integrations.sentinel import log_to_sentinel

logger = get_module_logger()


def log_group_action(payload: Dict[str, Any]) -> None:
    """Log group membership action to Sentinel for audit trail."""
    # Expect the new nested event contract where the original request is
    # provided under the 'request' key and orchestration details under
    # 'orchestration'. Fall back to top-level keys only if the structure
    # isn't present (defensive but tests will be updated to pass the new
    # contract).
    req = payload.get("request") or {}
    orch = payload.get("orchestration") or payload.get("result")

    # Determine action type from the event_type or orchestration keys
    action_type = "unknown"
    if "added" in str(payload.get("event_type", "")):
        action_type = "member_added"
    elif "removed" in str(payload.get("event_type", "")):
        action_type = "member_removed"

    audit_event = {
        "event_type": "group_membership_change",
        "action": action_type,
        "timestamp": datetime.utcnow().isoformat(),
        "group_id": req.get("group_id") or payload.get("group_id"),
        "member_email": req.get("member_email") or payload.get("member_email"),
        "requestor_email": req.get("requestor")
        or payload.get("requestor_email")
        or payload.get("requestor"),
        "provider": req.get("provider") or payload.get("provider"),
        "justification": req.get("justification") or payload.get("justification"),
        "success": bool(orch),
        "result_details": orch,
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
