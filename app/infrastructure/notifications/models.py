"""Notification system core models.

Platform-agnostic notification models for centralized dispatch.
Features define message content, infrastructure handles delivery.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class NotificationPriority(Enum):
    """Notification priority levels.

    Used to determine urgency and routing behavior.
    URGENT priority may trigger all channels (Slack + Email + SMS).
    """

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(Enum):
    """Notification delivery status.

    Tracks delivery attempt outcome for observability.
    """

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class Recipient:
    """Notification recipient information.

    Email is the universal identifier across platforms.
    Platform-specific IDs (slack_user_id, phone_number) are resolved
    by NotificationChannel implementations as needed.

    Attributes:
        email: User's email address (required, universal ID)
        slack_user_id: Resolved Slack user ID (optional)
        phone_number: Phone number for SMS (optional, format: +1234567890)
        preferred_channels: List of preferred channel names (default: ["chat"])

    Example:
        recipient = Recipient(
            email="user@example.com",
            preferred_channels=["chat", "email"]
        )
    """

    email: str
    slack_user_id: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_channels: List[str] = field(default_factory=lambda: ["chat"])

    def __post_init__(self):
        """Validate recipient data."""
        if not self.email:
            raise ValueError("Recipient email is required")
        if not isinstance(self.email, str) or "@" not in self.email:
            raise ValueError(f"Invalid email format: {self.email}")


@dataclass
class Notification:
    """Platform-agnostic notification message.

    Features format message content. Infrastructure handles delivery
    through appropriate channels with fallback support.

    Attributes:
        subject: Subject line (email), card title (chat), ignored (SMS)
        message: Plain text message body (required)
        recipients: List of Recipient objects (required)
        priority: Notification urgency level
        html_body: HTML email body (optional, email channel only)
        attachments: File attachments (optional, future feature)
        metadata: Feature-specific context data
        channels: Target channel names (default: ["chat"])
        retry_on_failure: Enable automatic retry (default: True)
        idempotency_key: Prevent duplicate sends (recommended)

    Example:
        notification = Notification(
            subject="Group Membership Update",
            message="You were added to group-name",
            recipients=[Recipient(email="user@example.com")],
            channels=["chat", "email"],
            priority=NotificationPriority.NORMAL,
            idempotency_key="group_added_12345_user@example.com"
        )
    """

    subject: str
    message: str
    recipients: List[Recipient]
    priority: NotificationPriority = NotificationPriority.NORMAL

    # Optional rich content
    html_body: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Delivery options
    channels: List[str] = field(default_factory=lambda: ["chat"])
    retry_on_failure: bool = True
    idempotency_key: Optional[str] = None

    def __post_init__(self):
        """Validate notification data."""
        if not self.recipients:
            raise ValueError("At least one recipient is required")
        if not self.message:
            raise ValueError("Message body is required")
        if not isinstance(self.recipients, list):
            raise ValueError("Recipients must be a list")
        if not all(isinstance(r, Recipient) for r in self.recipients):
            raise ValueError("All recipients must be Recipient objects")


@dataclass
class NotificationResult:
    """Result of notification delivery attempt.

    Returned by NotificationChannel.send() for observability.
    One result per recipient per channel.

    Attributes:
        notification: Original notification object
        channel: Channel name used for delivery
        status: Delivery outcome status
        message: Success or error message
        error_code: Optional error code for categorization
        retry_after: Seconds to wait before retry (optional)
        external_id: Platform-specific message ID (Slack ts, Gmail message_id, etc.)
        platform_response: Raw platform API response (for debugging)

    Example:
        result = NotificationResult(
            notification=notification,
            channel="chat",
            status=NotificationStatus.SENT,
            message="Sent to user@example.com",
            external_id="1234567890.123456",
            platform_response={"ts": "1234567890.123456"}
        )
    """

    notification: Notification
    channel: str
    status: NotificationStatus
    message: str
    error_code: Optional[str] = None
    retry_after: Optional[int] = None
    external_id: Optional[str] = None
    platform_response: Optional[Dict[str, Any]] = None

    @property
    def is_success(self) -> bool:
        """Check if delivery was successful."""
        return self.status == NotificationStatus.SENT
