"""Unit tests for EmailChannel (Gmail implementation)."""

import pytest
from unittest.mock import MagicMock, patch

from infrastructure.notifications.channels.email import EmailChannel
from infrastructure.notifications.models import (
    Notification,
    NotificationResult,
    NotificationStatus,
    NotificationPriority,
    Recipient,
)
from infrastructure.operations import OperationResult


@pytest.mark.unit
class TestEmailChannel:
    """Tests for EmailChannel implementation."""

    @pytest.fixture
    def email_channel(self, mock_gmail_next):
        """Create EmailChannel instance with mocked dependencies.

        Args:
            mock_gmail_next: Mock gmail_next fixture

        Returns:
            EmailChannel instance with gmail_next mocked
        """
        with patch(
            "infrastructure.notifications.channels.email.gmail_next",
            mock_gmail_next,
        ):
            channel = EmailChannel()
            yield channel

    def test_channel_name(self, email_channel):
        """Channel name returns 'email'."""
        assert email_channel.channel_name == "email"

    def test_send_success(self, email_channel, notification_factory, mock_gmail_next):
        """Successfully sends email to recipient."""
        notification = notification_factory(
            subject="Test Subject",
            message="Test email body",
            channels=["email"],
        )

        results = email_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.SENT
        assert result.channel == "email"
        assert "test@example.com" in result.message
        assert result.external_id == "msg_12345"

        # Verify Gmail API was called
        mock_gmail_next.send_email.assert_called_once()

    def test_send_recipient_resolution_failed(
        self, email_channel, notification_factory
    ):
        """Handles invalid email address."""
        # Create recipient with invalid email
        recipient = Recipient.__new__(Recipient)
        recipient.email = "invalid-email"  # Missing @ symbol
        recipient.slack_user_id = None
        recipient.phone_number = None
        recipient.preferred_channels = ["email"]

        # Manually bypass Recipient validation for this test
        notification = Notification.__new__(Notification)
        notification.subject = "Test"
        notification.message = "Test"
        notification.recipients = [recipient]
        notification.priority = NotificationPriority.NORMAL
        notification.html_body = None
        notification.attachments = []
        notification.metadata = {}
        notification.channels = ["email"]
        notification.retry_on_failure = True
        notification.idempotency_key = None

        results = email_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.FAILED
        assert result.error_code == "RECIPIENT_RESOLUTION_FAILED"

    def test_send_gmail_api_error(
        self, email_channel, notification_factory, mock_gmail_next
    ):
        """Handles Gmail API error during sending."""
        # Configure mock to return error OperationResult
        mock_gmail_next.send_email.return_value = OperationResult.transient_error(
            message="API Error",
            error_code="GMAIL_API_ERROR",
        )

        notification = notification_factory(message="Test message")

        results = email_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.FAILED
        assert result.error_code is not None

    def test_send_multiple_recipients(
        self, email_channel, notification_factory, recipient_factory
    ):
        """Sends emails to multiple recipients."""
        recipients = [recipient_factory(email=f"user{i}@example.com") for i in range(3)]
        notification = notification_factory(
            message="Test message", recipients=recipients
        )

        results = email_channel.send(notification)

        assert len(results) == 3
        assert all(r.status == NotificationStatus.SENT for r in results)

    def test_send_with_html_body(
        self, email_channel, notification_factory, mock_gmail_next
    ):
        """Sends email with HTML body."""
        notification = notification_factory(
            subject="HTML Email",
            message="Plain text version",
            html_body="<h1>HTML Version</h1><p>Rich content</p>",
        )

        results = email_channel.send(notification)

        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT

        # Verify Gmail API was called (implementation handles HTML internally)
        mock_gmail_next.send_email.assert_called_once()

    def test_resolve_recipient_valid_email(self, email_channel, recipient_factory):
        """Validates and returns valid email address."""
        recipient = recipient_factory(email="valid@example.com")

        result = email_channel.resolve_recipient(recipient)

        assert result.is_success is True
        assert result.data["email"] == "valid@example.com"
        assert "validated" in result.message.lower()

    def test_resolve_recipient_missing_email(self, email_channel):
        """Returns error when email is missing."""
        # Create recipient without email
        recipient = Recipient.__new__(Recipient)
        recipient.email = None
        recipient.slack_user_id = None
        recipient.phone_number = None
        recipient.preferred_channels = ["email"]

        result = email_channel.resolve_recipient(recipient)

        assert result.is_success is False
        assert result.error_code == "MISSING_EMAIL"
        assert "Email" in result.message and "required" in result.message

    def test_resolve_recipient_invalid_email_format(self, email_channel):
        """Returns error for invalid email format."""
        # Create recipient with invalid email
        recipient = Recipient.__new__(Recipient)
        recipient.email = "not-an-email"
        recipient.slack_user_id = None
        recipient.phone_number = None
        recipient.preferred_channels = ["email"]

        result = email_channel.resolve_recipient(recipient)

        assert result.is_success is False
        assert result.error_code == "INVALID_EMAIL"

    def test_health_check_success(self, email_channel, mock_gmail_next):
        """Health check succeeds when Gmail API is accessible."""
        # list_messages is already mocked in the fixture with success response
        result = email_channel.health_check()

        assert result.is_success is True
        assert "Gmail API healthy" in result.message
        mock_gmail_next.list_messages.assert_called_once()

    def test_health_check_failure(self, email_channel, mock_gmail_next):
        """Health check fails when Gmail API is inaccessible."""
        # Configure mock to return error OperationResult
        mock_gmail_next.list_messages.return_value = OperationResult.transient_error(
            message="API unavailable",
            error_code="API_ERROR",
        )

        result = email_channel.health_check()

        assert result.is_success is False
        assert "API unavailable" in result.message

    def test_send_with_priority(
        self, email_channel, notification_factory, mock_gmail_next
    ):
        """Sends email with different priority levels."""
        for priority in [
            NotificationPriority.LOW,
            NotificationPriority.NORMAL,
            NotificationPriority.HIGH,
            NotificationPriority.URGENT,
        ]:
            notification = notification_factory(
                subject=f"Priority {priority.value}",
                message="Test message",
                priority=priority,
            )

            results = email_channel.send(notification)

            assert len(results) == 1
            assert results[0].status == NotificationStatus.SENT

    @pytest.mark.skip(
        reason="Circuit breaker is mocked in unit tests - test behavior in integration tests"
    )
    def test_circuit_breaker_integration(
        self, email_channel, notification_factory, mock_gmail_next
    ):
        """Circuit breaker protects against repeated failures."""
        # Configure mock to always return error
        mock_gmail_next.send_email.return_value = OperationResult.transient_error(
            message="Persistent error",
            error_code="PERSISTENT_ERROR",
        )

        notification = notification_factory(message="Test")

        # Send multiple notifications to trigger circuit breaker
        for _ in range(6):  # Threshold is 5
            results = email_channel.send(notification)
            assert len(results) == 1
            assert results[0].status == NotificationStatus.FAILED

    def test_send_logs_success(
        self, email_channel, notification_factory, mock_gmail_next, caplog
    ):
        """Successful sends are logged."""
        notification = notification_factory(subject="Log Test")

        with caplog.at_level("INFO"):
            email_channel.send(notification)

        assert "gmail_sent" in caplog.text
        assert "test@example.com" in caplog.text

    def test_send_logs_failure(
        self, email_channel, notification_factory, mock_gmail_next, caplog
    ):
        """Failed sends are logged with error level."""
        mock_gmail_next.send_email.return_value = OperationResult.transient_error(
            message="Send failed",
            error_code="SEND_ERROR",
        )

        notification = notification_factory(message="Test")

        with caplog.at_level("ERROR"):
            email_channel.send(notification)

        assert "gmail_failed" in caplog.text

    def test_resolve_recipient_empty_email(self, email_channel):
        """Returns error for empty string email."""
        recipient = Recipient.__new__(Recipient)
        recipient.email = ""
        recipient.slack_user_id = None
        recipient.phone_number = None
        recipient.preferred_channels = ["email"]

        result = email_channel.resolve_recipient(recipient)

        assert result.is_success is False
        assert result.error_code in ["MISSING_EMAIL", "INVALID_EMAIL"]

    def test_send_respects_sender_config(
        self, email_channel, notification_factory, mock_gmail_next
    ):
        """Uses configured sender email address."""
        notification = notification_factory(message="Test")

        email_channel.send(notification)

        # Verify the sender was set from config
        assert email_channel._sender_email is not None
        mock_gmail_next.send_email.assert_called_once()
