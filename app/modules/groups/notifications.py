# modules/groups/notifications.py
from typing import Dict, Any

from core.logging import get_module_logger

logger = get_module_logger()


def send_group_notifications(payload: Dict[str, Any]) -> None:
    """Send notifications for group membership changes."""

    action = (
        "added to" if "added" in str(payload.get("event_type", "")) else "removed from"
    )

    try:
        # Send notification to requester
        _send_slack_notification(
            user_email=payload.get("requestor_email"),
            message=f"✅ Successfully {action} {payload.get('member_email')} {action.split()[1]} group {payload.get('group_id')}",
            provider=payload.get("provider"),
        )

        # Send notification to member being added/removed (if different from requester)
        member_email = payload.get("member_email")
        requestor_email = payload.get("requestor_email")

        if member_email and member_email != requestor_email:
            _send_slack_notification(
                user_email=member_email,
                message=f"📋 You have been {action} group {payload.get('group_id')} by {requestor_email}",
                provider=payload.get("provider"),
            )

        logger.info("Successfully sent group membership notifications")

    except (ConnectionError, TimeoutError, ValueError) as e:
        logger.error(f"Failed to send group membership notifications: {e}")


def _send_slack_notification(user_email: str, message: str, provider: str) -> None:
    """Send a Slack notification to a user."""
    try:
        # For now, we'll implement a simplified version that logs the notification
        # In a full implementation, you'd need to get the Slack client and send the message
        logger.info(
            "slack_notification_queued",
            user_email=user_email,
            message=f"🔐 **{provider.upper()} Group Membership Update**\n\n{message}",
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
    action = (
        "added to" if "added" in str(payload.get("event_type", "")) else "removed from"
    )

    message = f"""
Group Membership Update:

• Member: {payload.get('member_email')}
• Action: {action}
• Group: {payload.get('group_id')}
• Provider: {payload.get('provider', 'Unknown')}
• Requested by: {payload.get('requestor_email')}
• Justification: {payload.get('justification', 'Not provided')}
• Timestamp: {payload.get('timestamp', 'Unknown')}
"""

    return message.strip()
