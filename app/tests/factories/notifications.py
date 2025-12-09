"""Test factories for notification infrastructure.

Factory functions for creating test data for the notification system,
following the patterns established in tests/factories/commands.py.

All factories return Pydantic models for type safety and validation.
"""

from typing import List, Optional, Dict, Any
from infrastructure.notifications.models import (
    Notification,
    Recipient,
    NotificationPriority,
    NotificationStatus,
    NotificationResult,
)


def make_recipient(
    email: str = "user@example.com",
    slack_user_id: Optional[str] = None,
    phone_number: Optional[str] = None,
    preferred_channels: Optional[List[str]] = None,
) -> Recipient:
    """Create a test Recipient instance.

    Args:
        email: User's email address (default: user@example.com)
        slack_user_id: Optional Slack user ID
        phone_number: Optional phone in E.164 format
        preferred_channels: List of preferred channel names

    Returns:
        Recipient instance

    Example:
        >>> recipient = make_recipient(
        ...     email="alice@example.com",
        ...     slack_user_id="U12345",
        ...     preferred_channels=["chat", "email"]
        ... )
    """
    return Recipient(
        email=email,
        slack_user_id=slack_user_id,
        phone_number=phone_number,
        preferred_channels=preferred_channels or ["chat"],
    )


def make_notification(
    subject: str = "Test Notification",
    message: str = "This is a test notification message",
    recipients: Optional[List[Recipient]] = None,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    channels: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    retry_on_failure: bool = True,
    idempotency_key: Optional[str] = None,
) -> Notification:
    """Create a test Notification instance.

    Args:
        subject: Notification subject
        message: Plain text message body
        recipients: List of recipients (creates default if None)
        priority: Notification priority level
        channels: List of channel names to use
        metadata: Additional context data
        html_body: Optional HTML version of message
        attachments: File attachments (future feature)
        retry_on_failure: Enable automatic retry
        idempotency_key: Key for preventing duplicates

    Returns:
        Notification instance

    Example:
        >>> notification = make_notification(
        ...     subject="Access Granted",
        ...     message="You were added to engineering-team",
        ...     recipients=[make_recipient(email="alice@example.com")],
        ...     priority=NotificationPriority.HIGH,
        ...     channels=["chat", "email"],
        ...     idempotency_key="group_add_12345_alice@example.com"
        ... )
    """
    if recipients is None:
        recipients = [make_recipient()]

    return Notification(
        subject=subject,
        message=message,
        recipients=recipients,
        priority=priority,
        channels=channels or ["chat"],
        metadata=metadata or {},
        html_body=html_body,
        attachments=attachments or [],
        retry_on_failure=retry_on_failure,
        idempotency_key=idempotency_key,
    )


def make_notification_result(
    notification: Optional[Notification] = None,
    channel: str = "chat",
    status: NotificationStatus = NotificationStatus.SENT,
    message: str = "Notification sent successfully",
    error_code: Optional[str] = None,
    external_id: Optional[str] = None,
    retry_after: Optional[int] = None,
    platform_response: Optional[Dict[str, Any]] = None,
) -> NotificationResult:
    """Create a test NotificationResult instance.

    Args:
        notification: Original notification (creates default if None)
        channel: Channel name used
        status: Delivery status
        message: Result message
        error_code: Optional error code
        external_id: External platform ID
        retry_after: Seconds to wait before retry
        platform_response: Raw platform API response

    Returns:
        NotificationResult instance

    Example:
        >>> result = make_notification_result(
        ...     channel="chat",
        ...     status=NotificationStatus.SENT,
        ...     message="Sent to Slack user U12345",
        ...     external_id="1234567890.123456"
        ... )
    """
    if notification is None:
        notification = make_notification()

    return NotificationResult(
        notification=notification,
        channel=channel,
        status=status,
        message=message,
        error_code=error_code,
        external_id=external_id,
        retry_after=retry_after,
        platform_response=platform_response,
    )


def make_recipients(
    n: int = 3, domain: str = "example.com", prefix: str = "user"
) -> List[Recipient]:
    """Create multiple test recipients.

    Args:
        n: Number of recipients to create
        domain: Email domain
        prefix: Email prefix (will be suffixed with number)

    Returns:
        List of Recipient instances

    Example:
        >>> recipients = make_recipients(n=2, prefix="eng")
        >>> [r.email for r in recipients]
        ['eng1@example.com', 'eng2@example.com']
    """
    return [
        make_recipient(
            email=f"{prefix}{i}@{domain}",
            slack_user_id=f"U{i:05d}",
        )
        for i in range(1, n + 1)
    ]


def make_group_notification(
    group_id: str = "engineering-team",
    member_email: str = "user@example.com",
    requestor_email: str = "admin@example.com",
    action: str = "added to",
    provider: str = "google",
) -> Notification:
    """Create a notification for group membership changes.

    Convenience factory for groups module notifications following
    the pattern in modules/groups/infrastructure/notifications.py.

    Args:
        group_id: Group identifier
        member_email: Member being added/removed
        requestor_email: User performing the action
        action: Action description ("added to" or "removed from")
        provider: Provider name (google, aws)

    Returns:
        Notification instance configured for groups operations

    Example:
        >>> notification = make_group_notification(
        ...     group_id="eng-team",
        ...     member_email="alice@example.com",
        ...     requestor_email="admin@example.com",
        ...     action="added to",
        ...     provider="google"
        ... )
    """
    provider_display = provider.upper()
    message = (
        f"✅ Successfully {action} {member_email} {action.split()[1]} group {group_id}"
    )

    return make_notification(
        subject=f"{provider_display} Group Membership Update",
        message=message,
        recipients=[make_recipient(email=requestor_email)],
        channels=["chat"],
        priority=NotificationPriority.NORMAL,
        metadata={
            "group_id": group_id,
            "member_email": member_email,
            "requestor": requestor_email,
            "action": action.replace(" ", "_"),
            "provider": provider,
        },
        idempotency_key=f"groups_notif_{group_id}_{member_email}_{action.replace(' ', '_')}",
    )
