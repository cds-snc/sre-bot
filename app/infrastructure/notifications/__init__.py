"""Centralized notification dispatcher.

Provides multi-channel notification delivery (Slack, Email, SMS) with:
- Automatic channel selection and fallback
- Idempotency (prevents duplicates)
- Circuit breakers for resilience
- Recipient resolution
- Priority-based routing

Usage:
    from infrastructure.notifications import (
        Notification,
        Recipient,
        NotificationPriority,
        ChatChannel,
    )

    # Feature-level: Format message
    notification = Notification(
        subject="You were added to engineering-team",
        message="You were added to engineering-team",
        recipients=[Recipient(email="user@example.com")],
        channels=["chat", "email"],
        priority=NotificationPriority.NORMAL,
        idempotency_key="group_add_123_user@example.com"
    )

    # Infrastructure-level: Send via channel
    channel = ChatChannel()
    results = channel.send(notification)

    # Check results
    success = sum(1 for r in results if r.is_success)
    logger.info(f"Sent {success}/{len(results)} notifications")

Recommended Usage (Service Pattern with DI):
    from infrastructure.services import NotificationServiceDep

    @router.post("/notify")
    def send_notification(
        notification_service: NotificationServiceDep,
        notification: Notification
    ):
        results = notification_service.send(notification)
        success_count = sum(1 for r in results if r.is_success)
        return {"sent": success_count, "total": len(results)}
"""

# Models
from infrastructure.notifications.models import (
    Notification,
    Recipient,
    NotificationResult,
    NotificationPriority,
    NotificationStatus,
)

# Service (preferred)
from infrastructure.notifications.service import NotificationService

# Dispatcher (legacy, use NotificationService instead)
from infrastructure.notifications.dispatcher import NotificationDispatcher

# Channel interface
from infrastructure.notifications.channels.base import NotificationChannel

# Channel implementations
from infrastructure.notifications.channels.chat import ChatChannel
from infrastructure.notifications.channels.email import EmailChannel
from infrastructure.notifications.channels.sms import SMSChannel

# Export all public interfaces
__all__ = [
    # Models
    "Notification",
    "Recipient",
    "NotificationResult",
    "NotificationPriority",
    "NotificationStatus",
    # Dispatcher
    "NotificationDispatcher",
    # Channel interface
    "NotificationChannel",
    # Channel implementations
    "ChatChannel",
    "EmailChannel",
    "SMSChannel",
    # Service
    "NotificationService",
]
