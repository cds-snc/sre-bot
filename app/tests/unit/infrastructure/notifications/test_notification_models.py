"""Unit tests for notification models."""

import pytest

from infrastructure.notifications.models import (
    Notification,
    Recipient,
    NotificationResult,
    NotificationPriority,
    NotificationStatus,
)


@pytest.mark.unit
class TestRecipient:
    """Tests for Recipient model."""

    def test_recipient_creation_with_email_only(self):
        """Recipient can be created with email only."""
        recipient = Recipient(email="test@example.com")

        assert recipient.email == "test@example.com"
        assert recipient.slack_user_id is None
        assert recipient.phone_number is None
        assert recipient.preferred_channels == ["chat"]

    def test_recipient_creation_with_all_fields(self):
        """Recipient can be created with all fields."""
        recipient = Recipient(
            email="test@example.com",
            slack_user_id="U123456",
            phone_number="+1234567890",
            preferred_channels=["chat", "email", "sms"],
        )

        assert recipient.email == "test@example.com"
        assert recipient.slack_user_id == "U123456"
        assert recipient.phone_number == "+1234567890"
        assert recipient.preferred_channels == ["chat", "email", "sms"]

    def test_recipient_requires_email(self):
        """Recipient creation fails without email."""
        with pytest.raises(ValueError, match="email is required"):
            Recipient(email="")

    def test_recipient_validates_email_format(self):
        """Recipient validates email format."""
        with pytest.raises(ValueError, match="Invalid email format"):
            Recipient(email="invalid-email")

    def test_recipient_default_preferred_channels(self):
        """Recipient defaults to chat channel."""
        recipient = Recipient(email="user@example.com")
        assert recipient.preferred_channels == ["chat"]


@pytest.mark.unit
class TestNotification:
    """Tests for Notification model."""

    def test_notification_creation_with_minimal_fields(self, recipient_factory):
        """Notification can be created with minimal required fields."""
        recipient = recipient_factory()
        notification = Notification(
            subject="Test Subject",
            message="Test message",
            recipients=[recipient],
        )

        assert notification.subject == "Test Subject"
        assert notification.message == "Test message"
        assert len(notification.recipients) == 1
        assert notification.priority == NotificationPriority.NORMAL
        assert notification.channels == ["chat"]
        assert notification.retry_on_failure is True
        assert notification.html_body is None
        assert notification.idempotency_key is None

    def test_notification_creation_with_all_fields(self, recipient_factory):
        """Notification can be created with all fields."""
        recipients = [recipient_factory(email=f"user{i}@example.com") for i in range(3)]

        notification = Notification(
            subject="Important Update",
            message="Urgent message",
            recipients=recipients,
            priority=NotificationPriority.URGENT,
            html_body="<p>Urgent message</p>",
            metadata={"feature": "groups", "operation": "add_member"},
            channels=["chat", "email", "sms"],
            retry_on_failure=False,
            idempotency_key="unique-key-123",
        )

        assert notification.subject == "Important Update"
        assert notification.message == "Urgent message"
        assert notification.priority == NotificationPriority.URGENT
        assert len(notification.recipients) == 3
        assert notification.channels == ["chat", "email", "sms"]
        assert notification.idempotency_key == "unique-key-123"
        assert notification.html_body == "<p>Urgent message</p>"
        assert notification.metadata == {"feature": "groups", "operation": "add_member"}
        assert notification.retry_on_failure is False

    def test_notification_requires_recipients(self):
        """Notification creation fails without recipients."""
        with pytest.raises(ValueError, match="At least one recipient is required"):
            Notification(
                subject="Test",
                message="Test",
                recipients=[],
            )

    def test_notification_requires_message(self, recipient_factory):
        """Notification creation fails without message."""
        with pytest.raises(ValueError, match="Message body is required"):
            Notification(
                subject="Test",
                message="",
                recipients=[recipient_factory()],
            )

    def test_notification_validates_recipients_list(self, recipient_factory):
        """Notification validates recipients is a list."""
        with pytest.raises(ValueError, match="Recipients must be a list"):
            Notification(
                subject="Test",
                message="Test message",
                recipients=recipient_factory(),  # Single object, not list
            )

    def test_notification_validates_recipient_types(self):
        """Notification validates all recipients are Recipient objects."""
        with pytest.raises(
            ValueError, match="All recipients must be Recipient objects"
        ):
            Notification(
                subject="Test",
                message="Test message",
                recipients=["not-a-recipient-object"],
            )

    def test_notification_priority_enum(self, recipient_factory):
        """Notification priority uses enum values."""
        notification = Notification(
            subject="Test",
            message="Test",
            recipients=[recipient_factory()],
            priority=NotificationPriority.HIGH,
        )

        assert notification.priority == NotificationPriority.HIGH
        assert notification.priority.value == "high"

    def test_notification_default_metadata(self, recipient_factory):
        """Notification defaults to empty metadata dict."""
        notification = Notification(
            subject="Test",
            message="Test",
            recipients=[recipient_factory()],
        )

        assert notification.metadata == {}
        assert isinstance(notification.metadata, dict)


@pytest.mark.unit
class TestNotificationResult:
    """Tests for NotificationResult model."""

    def test_notification_result_creation(self, notification_factory):
        """NotificationResult can be created."""
        notification = notification_factory()

        result = NotificationResult(
            notification=notification,
            channel="chat",
            status=NotificationStatus.SENT,
            message="Successfully sent",
        )

        assert result.notification == notification
        assert result.channel == "chat"
        assert result.status == NotificationStatus.SENT
        assert result.message == "Successfully sent"
        assert result.is_success is True
        assert result.error_code is None

    def test_notification_result_is_success_property(self, notification_factory):
        """is_success property correctly identifies successful sends."""
        notification = notification_factory()

        success_result = NotificationResult(
            notification=notification,
            channel="email",
            status=NotificationStatus.SENT,
            message="Sent",
        )

        failed_result = NotificationResult(
            notification=notification,
            channel="email",
            status=NotificationStatus.FAILED,
            message="Failed to send",
            error_code="API_ERROR",
        )

        assert success_result.is_success is True
        assert failed_result.is_success is False

    def test_notification_result_with_error_code(self, notification_factory):
        """NotificationResult can include error codes."""
        notification = notification_factory()

        result = NotificationResult(
            notification=notification,
            channel="sms",
            status=NotificationStatus.FAILED,
            message="Recipient not found",
            error_code="RECIPIENT_NOT_FOUND",
        )

        assert result.error_code == "RECIPIENT_NOT_FOUND"
        assert result.is_success is False

    def test_notification_result_with_external_id(self, notification_factory):
        """NotificationResult can include external platform IDs."""
        notification = notification_factory()

        result = NotificationResult(
            notification=notification,
            channel="chat",
            status=NotificationStatus.SENT,
            message="Sent",
            external_id="1234567890.123456",  # Slack timestamp
        )

        assert result.external_id == "1234567890.123456"

    def test_notification_result_with_retry_after(self, notification_factory):
        """NotificationResult can include retry delay."""
        notification = notification_factory()

        result = NotificationResult(
            notification=notification,
            channel="email",
            status=NotificationStatus.FAILED,
            message="Rate limited",
            error_code="RATE_LIMIT",
            retry_after=60,
        )

        assert result.retry_after == 60
        assert result.error_code == "RATE_LIMIT"


@pytest.mark.unit
class TestNotificationPriority:
    """Tests for NotificationPriority enum."""

    def test_priority_values(self):
        """Priority enum has correct values."""
        assert NotificationPriority.LOW.value == "low"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.URGENT.value == "urgent"

    def test_priority_comparison(self):
        """Priority enum values are accessible."""
        priorities = [p.value for p in NotificationPriority]
        assert "low" in priorities
        assert "normal" in priorities
        assert "high" in priorities
        assert "urgent" in priorities


@pytest.mark.unit
class TestNotificationStatus:
    """Tests for NotificationStatus enum."""

    def test_status_values(self):
        """Status enum has correct values."""
        assert NotificationStatus.PENDING.value == "pending"
        assert NotificationStatus.SENT.value == "sent"
        assert NotificationStatus.FAILED.value == "failed"
        assert NotificationStatus.RETRYING.value == "retrying"

    def test_status_types(self):
        """Status enum values are accessible."""
        statuses = [s.value for s in NotificationStatus]
        assert "pending" in statuses
        assert "sent" in statuses
        assert "failed" in statuses
        assert "retrying" in statuses
