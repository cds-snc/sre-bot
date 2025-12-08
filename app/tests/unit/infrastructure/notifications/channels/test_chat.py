"""Unit tests for ChatChannel (Slack implementation)."""

import pytest
from unittest.mock import patch
from pydantic import ValidationError
from slack_sdk.errors import SlackApiError

from infrastructure.notifications.channels.chat import ChatChannel
from infrastructure.notifications.models import (
    NotificationStatus,
    Recipient,
)


@pytest.mark.unit
class TestChatChannel:
    """Tests for ChatChannel implementation."""

    @pytest.fixture
    def chat_channel(self, mock_slack_client_manager, mock_circuit_breaker):
        """Create ChatChannel instance with mocked dependencies.

        Args:
            mock_slack_client_manager: Mock SlackClientManager fixture
            mock_circuit_breaker: Mock CircuitBreaker fixture

        Returns:
            ChatChannel instance
        """
        with (
            patch(
                "infrastructure.notifications.channels.chat.SlackClientManager",
                return_value=mock_slack_client_manager,
            ),
            patch(
                "infrastructure.notifications.channels.chat.CircuitBreaker",
                return_value=mock_circuit_breaker,
            ),
        ):
            return ChatChannel()

    def test_channel_name(self, chat_channel):
        """Channel name returns 'chat'."""
        assert chat_channel.channel_name == "chat"

    def test_send_success(self, chat_channel, notification_factory, mock_slack_client):
        """Successfully sends DM to recipient."""
        notification = notification_factory(
            subject="Test Subject",
            message="Test message",
            channels=["chat"],
        )

        results = chat_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.SENT
        assert result.channel == "chat"
        assert "test@example.com" in result.message
        assert result.external_id == "1234567890.123456"

        # Verify Slack API calls
        mock_slack_client.users_lookupByEmail.assert_called_once()
        mock_slack_client.conversations_open.assert_called_once()
        mock_slack_client.chat_postMessage.assert_called_once()

    def test_send_recipient_resolution_failed(
        self, chat_channel, notification_factory, mock_slack_client
    ):
        """Handles recipient resolution failure gracefully."""
        # Configure mock to fail user lookup
        mock_slack_client.users_lookupByEmail.side_effect = SlackApiError(
            message="user_not_found",
            response={"ok": False, "error": "users_not_found"},
        )

        notification = notification_factory(message="Test message")

        results = chat_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.FAILED
        assert result.error_code == "RECIPIENT_RESOLUTION_FAILED"
        assert "Failed to resolve recipient" in result.message

    def test_send_slack_api_error(
        self, chat_channel, notification_factory, mock_slack_client
    ):
        """Handles Slack API error during message sending."""
        # Configure mock to fail message sending
        mock_slack_client.chat_postMessage.side_effect = SlackApiError(
            message="channel_not_found",
            response={"ok": False, "error": "channel_not_found"},
        )

        notification = notification_factory(message="Test message")

        results = chat_channel.send(notification)

        assert len(results) == 1
        result = results[0]
        assert result.status == NotificationStatus.FAILED
        assert result.error_code is not None

    def test_send_multiple_recipients(
        self, chat_channel, notification_factory, recipient_factory
    ):
        """Sends notifications to multiple recipients."""
        recipients = [recipient_factory(email=f"user{i}@example.com") for i in range(3)]
        notification = notification_factory(
            message="Test message", recipients=recipients
        )

        results = chat_channel.send(notification)

        assert len(results) == 3
        assert all(r.status == NotificationStatus.SENT for r in results)

    def test_resolve_recipient_by_email(self, chat_channel, recipient_factory):
        """Resolves recipient by email address."""
        recipient = recipient_factory(email="test@example.com")

        result = chat_channel.resolve_recipient(recipient)

        assert result.is_success is True
        assert result.data["slack_user_id"] == "U12345TEST"
        assert "test@example.com" in result.message

    def test_resolve_recipient_by_slack_user_id(
        self, chat_channel, recipient_factory, mock_slack_client
    ):
        """Validates existing Slack user ID."""
        recipient = recipient_factory(
            email="test@example.com",
            slack_user_id="U12345TEST",
        )

        result = chat_channel.resolve_recipient(recipient)

        assert result.is_success is True
        assert result.data["slack_user_id"] == "U12345TEST"
        mock_slack_client.users_info.assert_called_once_with(user="U12345TEST")

    def test_resolve_recipient_slack_user_id_invalid(
        self, chat_channel, recipient_factory, mock_slack_client
    ):
        """Falls back to email lookup when Slack user ID is invalid."""
        # Configure mock to fail user_info but succeed on email lookup
        mock_slack_client.users_info.side_effect = SlackApiError(
            message="user_not_found",
            response={"ok": False, "error": "user_not_found"},
        )

        recipient = recipient_factory(
            email="test@example.com",
            slack_user_id="INVALID_ID",
        )

        result = chat_channel.resolve_recipient(recipient)

        # Should fall back to email lookup
        assert result.is_success is True
        assert result.data["slack_user_id"] == "U12345TEST"
        mock_slack_client.users_lookupByEmail.assert_called_once()

    def test_resolve_recipient_no_identifier(self, chat_channel):
        """Email is required by Pydantic at Recipient creation."""
        # Pydantic requires email field
        with pytest.raises(ValidationError, match="email"):
            Recipient(email=None)

    def test_resolve_recipient_email_not_found(
        self, chat_channel, recipient_factory, mock_slack_client
    ):
        """Handles email not found in Slack workspace."""
        mock_slack_client.users_lookupByEmail.side_effect = SlackApiError(
            message="users_not_found",
            response={"ok": False, "error": "users_not_found"},
        )

        recipient = recipient_factory(email="notfound@example.com")

        result = chat_channel.resolve_recipient(recipient)

        assert result.is_success is False
        assert result.error_code == "users_not_found"

    def test_health_check_success(self, chat_channel, mock_slack_client):
        """Health check succeeds with valid credentials."""
        result = chat_channel.health_check()

        assert result.is_success is True
        assert "Slack API healthy" in result.message
        assert result.data["team"] == "Test Team"
        assert result.data["user"] == "test_bot"
        mock_slack_client.auth_test.assert_called_once()

    def test_health_check_failure(self, chat_channel, mock_slack_client):
        """Health check fails with invalid credentials."""
        mock_slack_client.auth_test.return_value = {
            "ok": False,
            "error": "invalid_auth",
        }

        result = chat_channel.health_check()

        assert result.is_success is False
        assert "auth test failed" in result.message
        assert result.error_code == "invalid_auth"

    def test_health_check_exception(self, chat_channel, mock_slack_client):
        """Health check handles exceptions gracefully."""
        mock_slack_client.auth_test.side_effect = Exception("Connection error")

        result = chat_channel.health_check()

        assert result.is_success is False
        assert "Health check failed" in result.message
        assert "Connection error" in result.message

    def test_send_with_subject(
        self, chat_channel, notification_factory, mock_slack_client
    ):
        """Message includes subject as bold text."""
        notification = notification_factory(
            subject="Important Update",
            message="Please review this message.",
        )

        results = chat_channel.send(notification)

        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT

        # Verify message was formatted with subject
        call_args = mock_slack_client.chat_postMessage.call_args
        sent_text = call_args.kwargs["text"]
        assert "*Important Update*" in sent_text
        assert "Please review this message." in sent_text

    @pytest.mark.skip(
        reason="Circuit breaker is mocked in unit tests - test behavior in integration tests"
    )
    def test_circuit_breaker_integration(
        self, chat_channel, notification_factory, mock_slack_client
    ):
        """Circuit breaker protects against repeated failures."""
        # Configure mock to always fail
        mock_slack_client.chat_postMessage.side_effect = SlackApiError(
            message="error",
            response={"ok": False, "error": "internal_error"},
        )

        notification = notification_factory(message="Test")

        # Send multiple notifications to trigger circuit breaker
        for _ in range(6):  # Threshold is 5
            results = chat_channel.send(notification)
            assert len(results) == 1

        # After threshold, circuit breaker should be open
        # Verify the circuit breaker state (this tests integration)
        assert chat_channel._circuit_breaker.failure_count >= 5
