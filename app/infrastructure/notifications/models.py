"""Notification system core models.

Platform-agnostic notification models for centralized dispatch.
Features define message content, infrastructure handles delivery.

Uses Pydantic BaseModel for:
- RFC 5322 compliant email validation (EmailStr)
- Runtime input validation
- Type safety with proper error messages
- Consistency with API layer (modules/groups/api/schemas.py)
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, EmailStr, Field, field_validator


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


class Recipient(BaseModel):
    """Notification recipient information.

    Email is the universal identifier across platforms.
    Platform-specific IDs (slack_user_id, phone_number) are resolved
    by NotificationChannel implementations as needed.

    Uses Pydantic for robust email validation (RFC 5322 compliant).

    Attributes:
        email: User's email address (required, validated with EmailStr)
        slack_user_id: Resolved Slack user ID (optional)
        phone_number: Phone number for SMS (optional, format: +1234567890)
        preferred_channels: List of preferred channel names (default: ["chat"])

    Example:
        recipient = Recipient(
            email="user@example.com",
            preferred_channels=["chat", "email"]
        )
    """

    email: EmailStr
    slack_user_id: Optional[str] = None
    phone_number: Optional[str] = None
    preferred_channels: List[str] = Field(default_factory=lambda: ["chat"])

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Validate E.164 phone format if provided."""
        if v is None:
            return v
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError(f"Phone number must be in E.164 format: {v}")
        if len(v) < 8 or len(v) > 16:
            raise ValueError(f"Phone number length invalid: {v}")
        return v


class Notification(BaseModel):
    """Platform-agnostic notification message.

    Features format message content. Infrastructure handles delivery
    through appropriate channels with fallback support.

    Uses Pydantic for validation of required fields and types.

    Attributes:
        subject: Subject line (email), card title (chat), ignored (SMS)
        message: Plain text message body (required)
        recipients: List of recipients (required, minimum 1)
        priority: NotificationPriority level (default: NORMAL)
        channels: List of channel names to use (default: ["chat"])
        metadata: Additional context (e.g., incident_id, correlation_id)
        html_body: Optional HTML version for email channel
        attachments: File attachments (future feature)
        retry_on_failure: Enable automatic retry (default: True)
        idempotency_key: Prevent duplicate sends (recommended)

    Example:
        notification = Notification(
            subject="Access Granted",
            message="You have been added to engineering-team",
            recipients=[Recipient(email="user@example.com")],
            priority=NotificationPriority.HIGH,
            channels=["chat", "email"],
            metadata={"group_id": "12345", "requestor": "admin@example.com"}
        )
    """

    subject: str
    message: str
    recipients: List[Recipient] = Field(..., min_length=1)
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[str] = Field(default_factory=lambda: ["chat"])
    metadata: Dict[str, Any] = Field(default_factory=dict)
    html_body: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    retry_on_failure: bool = True
    idempotency_key: Optional[str] = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Ensure message is not empty."""
        if not v or not v.strip():
            raise ValueError("Notification message cannot be empty")
        return v


class NotificationResult(BaseModel):
    """Result of notification delivery attempt.

    Returned by NotificationChannel.send() to track success/failure
    per recipient per channel.

    Uses Pydantic for type safety and validation.

    Attributes:
        notification: Original notification sent
        channel: Channel name used (e.g., "chat", "email", "sms")
        status: Delivery status (SENT, FAILED, RETRYING)
        message: Human-readable result message
        error_code: Optional error code for failures
        external_id: External platform ID (Slack ts, Gmail msg ID, etc.)
        retry_after: Seconds to wait before retry (rate limits)
        platform_response: Raw platform API response (debugging)

    Example:
        result = NotificationResult(
            notification=notification,
            channel="chat",
            status=NotificationStatus.SENT,
            message="Sent to Slack user U12345",
            external_id="1234567890.123456"
        )
    """

    notification: Notification
    channel: str
    status: NotificationStatus
    message: str
    error_code: Optional[str] = None
    external_id: Optional[str] = None
    retry_after: Optional[int] = None
    platform_response: Optional[Dict[str, Any]] = None

    @property
    def is_success(self) -> bool:
        """Check if delivery was successful."""
        return self.status == NotificationStatus.SENT

    model_config = {"arbitrary_types_allowed": True}
