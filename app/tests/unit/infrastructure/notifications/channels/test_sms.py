"""Unit tests for SMSChannel (GC Notify implementation)."""

import pytest
from unittest.mock import MagicMock, patch, Mock
from pydantic import ValidationError

from infrastructure.notifications.channels.sms import SMSChannel
from infrastructure.notifications.models import (
    NotificationStatus,
    NotificationPriority,
)


@pytest.mark.unit
class TestSMSChannel:
    """Tests for SMSChannel implementation."""

    @pytest.fixture
    def sms_channel(self, mock_settings):
        """Create SMSChannel instance.

        Args:
            mock_settings: Mock settings fixture

        Returns:
            SMSChannel instance
        """
        return SMSChannel(settings=mock_settings)

    def test_channel_name(self, sms_channel):
        """Channel name returns 'sms'."""
        assert sms_channel.channel_name == "sms"

    @patch("infrastructure.notifications.channels.sms.post_event")
    def test_send_success(
        self, mock_post_event, sms_channel, notification_factory, recipient_factory
    ):
        """Successfully sends SMS to recipient."""
        # Configure mock response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json = MagicMock(
            return_value={
                "id": "notification_12345",
                "reference": None,
                "content": {"body": "Test message"},
            }
        )
        mock_post_event.return_value = mock_response

        recipient = recipient_factory(
            email="test@example.com",
            phone_number="+15555551234",
        )
        notification = notification_factory(
            message="Test SMS message",
            recipients=[recipient],
            channels=["sms"],
        )

        results = sms_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.SENT
        assert result.channel == "sms"
        assert "+15555551234" in result.message
        assert result.external_id == "notification_12345"

        # Verify post_event was called
        mock_post_event.assert_called_once()

    def test_send_recipient_resolution_failed(
        self, sms_channel, notification_factory, recipient_factory
    ):
        """Handles missing phone number."""
        recipient = recipient_factory(
            email="test@example.com",
            phone_number=None,  # No phone number
        )
        notification = notification_factory(
            message="Test message",
            recipients=[recipient],
        )

        results = sms_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.FAILED
        assert result.error_code == "RECIPIENT_RESOLUTION_FAILED"
        assert "Failed to resolve recipient" in result.message

    @patch("infrastructure.notifications.channels.sms.post_event")
    def test_send_api_error(
        self, mock_post_event, sms_channel, notification_factory, recipient_factory
    ):
        """Handles GC Notify API error (400 response)."""
        # Configure mock to return error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json = MagicMock(
            return_value={
                "errors": [{"error": "BadRequestError", "message": "Invalid phone"}]
            }
        )
        mock_post_event.return_value = mock_response

        recipient = recipient_factory(
            email="test@example.com",
            phone_number="+15555551234",
        )
        notification = notification_factory(
            message="Test message",
            recipients=[recipient],
        )

        results = sms_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.FAILED
        assert result.error_code is not None

    @patch("infrastructure.notifications.channels.sms.post_event")
    def test_send_multiple_recipients(
        self, mock_post_event, sms_channel, notification_factory, recipient_factory
    ):
        """Sends SMS to multiple recipients."""
        # Configure mock response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json = MagicMock(return_value={"id": "notification_12345"})
        mock_post_event.return_value = mock_response

        recipients = [
            recipient_factory(
                email=f"user{i}@example.com",
                phone_number=f"+1555555{i:04d}",
            )
            for i in range(3)
        ]
        notification = notification_factory(
            message="Test message",
            recipients=recipients,
        )

        results = sms_channel.send(notification)

        assert len(results) == 3
        assert all(r.status == NotificationStatus.SENT for r in results)
        assert mock_post_event.call_count == 3

    def test_resolve_recipient_valid_phone(self, sms_channel, recipient_factory):
        """Validates phone number in E.164 format."""
        recipient = recipient_factory(
            email="test@example.com",
            phone_number="+15555551234",
        )

        result = sms_channel.resolve_recipient(recipient)

        assert result.is_success is True
        assert result.data["phone_number"] == "+15555551234"
        assert "validated" in result.message.lower()

    def test_resolve_recipient_missing_phone(self, sms_channel, recipient_factory):
        """Returns error when phone number is missing."""
        recipient = recipient_factory(
            email="test@example.com",
            phone_number=None,
        )

        result = sms_channel.resolve_recipient(recipient)

        assert result.is_success is False
        assert result.error_code == "MISSING_PHONE"
        assert "Phone number required" in result.message

    def test_resolve_recipient_invalid_format(self, sms_channel, recipient_factory):
        """Invalid phone format is rejected by Pydantic at Recipient creation."""
        # Pydantic rejects invalid phone numbers at construction time
        with pytest.raises(
            ValidationError, match="Phone number must be in E.164 format"
        ):
            recipient_factory(
                email="test@example.com",
                phone_number="5555551234",  # Missing + prefix
            )

    def test_resolve_recipient_invalid_length(self, sms_channel, recipient_factory):
        """Invalid phone length is rejected by Pydantic at Recipient creation."""
        # Pydantic rejects invalid phone length at construction time
        with pytest.raises(ValidationError, match="Phone number length invalid"):
            recipient_factory(
                email="test@example.com",
                phone_number="+1234567890123456",  # Too long (>15 digits)
            )

    def test_resolve_recipient_non_numeric(self, sms_channel, recipient_factory):
        """Non-numeric characters are rejected by Pydantic at Recipient creation."""
        # Pydantic rejects non-numeric phone numbers at construction time
        with pytest.raises(
            ValidationError, match="Phone number must be in E.164 format"
        ):
            recipient_factory(
                email="test@example.com",
                phone_number="+1-555-555-1234",  # Contains dashes
            )

    @patch("infrastructure.notifications.channels.sms.create_authorization_header")
    def test_health_check_success(self, mock_create_auth, sms_channel):
        """Health check succeeds when credentials are valid."""
        mock_create_auth.return_value = ("Authorization", "Bearer token123")

        result = sms_channel.health_check()

        assert result.is_success is True
        assert "credentials valid" in result.message
        assert "api_url" in result.data
        mock_create_auth.assert_called_once()

    @patch("infrastructure.notifications.channels.sms.create_authorization_header")
    def test_health_check_failure(self, mock_create_auth, sms_channel):
        """Health check fails when auth header creation fails."""
        mock_create_auth.return_value = (None, None)

        result = sms_channel.health_check()

        assert result.is_success is False
        assert "authorization header" in result.message.lower()

    @patch("infrastructure.notifications.channels.sms.create_authorization_header")
    def test_health_check_exception(self, mock_create_auth, sms_channel):
        """Health check handles exceptions gracefully."""
        mock_create_auth.side_effect = Exception("Connection error")

        result = sms_channel.health_check()

        assert result.is_success is False
        assert "Health check failed" in result.message
        assert "Connection error" in result.message

    @patch("infrastructure.notifications.channels.sms.post_event")
    def test_send_with_priority(
        self, mock_post_event, sms_channel, notification_factory, recipient_factory
    ):
        """Sends SMS with different priority levels."""
        # Configure mock response
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json = MagicMock(return_value={"id": "notification_12345"})
        mock_post_event.return_value = mock_response

        recipient = recipient_factory(
            email="test@example.com",
            phone_number="+15555551234",
        )

        for priority in [
            NotificationPriority.LOW,
            NotificationPriority.NORMAL,
            NotificationPriority.HIGH,
            NotificationPriority.URGENT,
        ]:
            notification = notification_factory(
                message="Test message",
                recipients=[recipient],
                priority=priority,
            )

            results = sms_channel.send(notification)

            assert len(results) == 1
            assert results[0].status == NotificationStatus.SENT

    @patch("infrastructure.notifications.channels.sms.post_event")
    @pytest.mark.skip(
        reason="Circuit breaker is mocked in unit tests - test behavior in integration tests"
    )
    def test_circuit_breaker_integration(
        self, mock_post_event, sms_channel, notification_factory, recipient_factory
    ):
        """Circuit breaker protects against repeated failures."""
        # Configure mock to always fail
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json = MagicMock(return_value={"error": "Internal error"})
        mock_post_event.return_value = mock_response

        recipient = recipient_factory(
            email="test@example.com",
            phone_number="+15555551234",
        )
        notification = notification_factory(
            message="Test",
            recipients=[recipient],
        )

        # Send multiple notifications to trigger circuit breaker
        for _ in range(6):  # Threshold is 5
            results = sms_channel.send(notification)
            assert len(results) == 1

        # After threshold, circuit breaker should be open
        assert sms_channel._circuit_breaker.failure_count >= 5

    @patch("infrastructure.notifications.channels.sms.post_event")
    def test_send_logs_success(
        self,
        mock_post_event,
        sms_channel,
        notification_factory,
        recipient_factory,
        caplog,
    ):
        """Successful sends are logged."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json = MagicMock(return_value={"id": "notification_12345"})
        mock_post_event.return_value = mock_response

        recipient = recipient_factory(
            email="test@example.com",
            phone_number="+15555551234",
        )
        notification = notification_factory(
            message="Test",
            recipients=[recipient],
        )

        with caplog.at_level("INFO"):
            sms_channel.send(notification)

        assert "sms_sent" in caplog.text
        assert "+15555551234" in caplog.text

    @patch("infrastructure.notifications.channels.sms.post_event")
    def test_send_logs_failure(
        self,
        mock_post_event,
        sms_channel,
        notification_factory,
        recipient_factory,
        caplog,
    ):
        """Failed sends are logged with error level."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json = MagicMock(return_value={"error": "Bad request"})
        mock_post_event.return_value = mock_response

        recipient = recipient_factory(
            email="test@example.com",
            phone_number="+15555551234",
        )
        notification = notification_factory(
            message="Test",
            recipients=[recipient],
        )

        with caplog.at_level("ERROR"):
            sms_channel.send(notification)

        assert "sms_failed" in caplog.text

    def test_resolve_recipient_valid_international_phone(
        self, sms_channel, recipient_factory
    ):
        """Validates international phone numbers."""
        test_numbers = [
            "+15555551234",  # US
            "+442071234567",  # UK
            "+33612345678",  # France
            "+81312345678",  # Japan
        ]

        for phone in test_numbers:
            recipient = recipient_factory(
                email="test@example.com",
                phone_number=phone,
            )

            result = sms_channel.resolve_recipient(recipient)

            assert result.is_success is True, f"Failed for {phone}"
            assert result.data["phone_number"] == phone
