# modules/groups/notifications.py
from typing import Dict, Any

from core.logging import get_module_logger
from infrastructure.events import Event

logger = get_module_logger()


def send_group_notifications(payload: Event) -> None:
    """Send notifications for group membership changes."""

    # Extract metadata which contains request and orchestration details
    event_dict = payload.to_dict()
    metadata = event_dict.get("metadata", {})
    req: dict = metadata.get("request", {})
    orch: dict = metadata.get("orchestration") or {}

    # Get action from orchestration
    action_type = orch.get("action", "")

    # Skip notifications for read-only operations like list_groups
    if action_type in ["list_groups", "get_details", "list_members"]:
        logger.debug(
            "skipping_notification_for_read_operation",
            action=action_type,
            event_type=event_dict.get("event_type"),
        )
        return

    # Determine notification message based on event type
    if "added" in str(event_dict.get("event_type", "")):
        action = "added to"
    elif "removed" in str(event_dict.get("event_type", "")):
        action = "removed from"
    else:
        # Unknown operation, skip notification
        logger.debug(
            "skipping_notification_for_unknown_operation",
            event_type=event_dict.get("event_type"),
        )
        return

    try:
        # Send notification to requester
        _send_slack_notification(
            user_email=req.get("requestor") or req.get("requestor_email"),
            message=f"✅ Successfully {action} {req.get('member_email')} {action.split()[1]} group {req.get('group_id')}",
            provider=req.get("provider") or orch.get("provider"),
        )

        # Send notification to member being added/removed (if different from requester)
        member_email = req.get("member_email")
        requestor_email = req.get("requestor") or req.get("requestor_email")

        if member_email and member_email != requestor_email:
            _send_slack_notification(
                user_email=member_email,
                message=f"📋 You have been {action} group {req.get('group_id')} by {requestor_email}",
                provider=req.get("provider") or orch.get("provider"),
            )

        logger.info("Successfully sent group membership notifications")

    except (ConnectionError, TimeoutError, ValueError) as e:
        logger.error(f"Failed to send group membership notifications: {e}")


def _send_slack_notification(user_email: str, message: str, provider: str) -> None:
    """Send a Slack notification to a user."""
    try:
        # For now, we'll implement a simplified version that logs the notification
        # In a full implementation, you'd need to get the Slack client and send the message
        provider_display = provider.upper() if provider else "UNKNOWN"
        logger.info(
            "slack_notification_queued",
            user_email=user_email,
            message=f"🔐 **{provider_display} Group Membership Update**\n\n{message}",
            provider=provider,
        )

    except (ConnectionError, TimeoutError, ValueError) as e:
        logger.error(f"Failed to send Slack notification to {user_email}: {e}")


def send_email_notification(user_email: str, subject: str, message: str) -> None:
    """Send email notification using Google Workspace Gmail service."""
    try:
        # Placeholder for email notification
        logger.info(
            f"Email notification queued for {user_email}: {subject} - {message[:50]}..."
        )

    except (ConnectionError, TimeoutError, ValueError) as e:
        logger.error(f"Failed to send email notification to {user_email}: {e}")


def format_group_update_message(payload: Dict[str, Any]) -> str:
    """Format a user-friendly message for group updates."""
    req = payload.get("request", {})
    orch = payload.get("orchestration") or {}

    action = (
        "added to" if "added" in str(payload.get("event_type", "")) else "removed from"
    )

    message = f"""
Group Membership Update:

• Member: {req.get('member_email')}
• Action: {action}
• Group: {req.get('group_id')}
• Provider: {req.get('provider', orch.get('provider', 'Unknown'))}
• Requested by: {req.get('requestor') or req.get('requestor_email')}
• Justification: {req.get('justification', 'Not provided')}
• Timestamp: {payload.get('timestamp', 'Unknown')}
"""

    return message.strip()
