"""Unit tests for NotificationDispatcher.

Tests cover:
- Multi-channel routing
- Automatic fallback on channel failure
- Idempotency cache integration
- Recipient-specific channel preferences
- Broadcast functionality
- Health checks
- Error handling
"""

import pytest
from unittest.mock import MagicMock

from infrastructure.notifications.dispatcher import NotificationDispatcher
from infrastructure.notifications.models import (
    NotificationStatus,
)
from infrastructure.operations import OperationResult, OperationStatus


@pytest.mark.unit
class TestNotificationDispatcherInitialization:
    """Tests for dispatcher initialization."""

    def test_dispatcher_creation_with_minimal_config(self, mock_notification_channel):
        """Test dispatcher can be created with just channels."""
        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel}
        )

        assert dispatcher.channels == {"chat": mock_notification_channel}
        assert dispatcher.fallback_order == ["chat", "email", "sms"]
        assert dispatcher.idempotency_cache is None

    def test_dispatcher_creation_with_custom_fallback_order(
        self, mock_notification_channel
    ):
        """Test custom fallback order is respected."""
        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel},
            fallback_order=["email", "chat"],
        )

        assert dispatcher.fallback_order == ["email", "chat"]

    def test_dispatcher_creation_with_idempotency_cache(
        self, mock_notification_channel
    ):
        """Test idempotency cache integration."""
        mock_cache = MagicMock()

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel},
            idempotency_cache=mock_cache,
            idempotency_ttl_seconds=7200,
        )

        assert dispatcher.idempotency_cache is mock_cache
        assert dispatcher.idempotency_ttl_seconds == 7200

    def test_get_available_channels(self, mock_notification_channel):
        """Test retrieving list of available channels."""
        dispatcher = NotificationDispatcher(
            channels={
                "chat": mock_notification_channel,
                "email": mock_notification_channel,
            }
        )

        channels = dispatcher.get_available_channels()

        assert set(channels) == {"chat", "email"}


@pytest.mark.unit
class TestNotificationDispatcherSend:
    """Tests for send() method."""

    def test_send_notification_single_channel_success(
        self,
        mock_notification_channel,
        notification_factory,
        notification_result_factory,
    ):
        """Test successful send through single channel."""
        notification = notification_factory(channels=["chat"])
        expected_result = notification_result_factory(
            notification=notification,
            channel="chat",
            status=NotificationStatus.SENT,
        )

        mock_notification_channel.channel_name = "chat"
        mock_notification_channel.send.return_value = [expected_result]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel}
        )
        results = dispatcher.send(notification)

        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT
        assert results[0].channel == "chat"
        mock_notification_channel.send.assert_called_once()

    def test_send_notification_multiple_recipients(
        self,
        mock_notification_channel,
        notification_factory,
        recipient_factory,
        notification_result_factory,
    ):
        """Test send to multiple recipients."""
        recipients = [
            recipient_factory(email="user1@example.com"),
            recipient_factory(email="user2@example.com"),
        ]
        notification = notification_factory(recipients=recipients, channels=["chat"])

        mock_notification_channel.channel_name = "chat"
        mock_notification_channel.send.return_value = [
            notification_result_factory(status=NotificationStatus.SENT)
        ]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel}
        )
        results = dispatcher.send(notification)

        # Called once per recipient
        assert mock_notification_channel.send.call_count == 2
        assert len(results) == 2

    def test_send_with_channel_fallback(
        self,
        notification_factory,
        notification_result_factory,
    ):
        """Test automatic fallback when primary channel fails."""
        notification = notification_factory(channels=["chat", "email"])

        # Mock chat channel that fails
        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"
        mock_chat.send.return_value = [
            notification_result_factory(
                channel="chat",
                status=NotificationStatus.FAILED,
                error_code="SLACK_API_ERROR",
            )
        ]

        # Mock email channel that succeeds
        mock_email = MagicMock()
        mock_email.channel_name = "email"
        mock_email.send.return_value = [
            notification_result_factory(
                channel="email",
                status=NotificationStatus.SENT,
            )
        ]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_chat, "email": mock_email}
        )
        results = dispatcher.send(notification)

        # Both channels should be tried
        mock_chat.send.assert_called_once()
        mock_email.send.assert_called_once()

        # Should have 2 results (1 failed chat, 1 successful email)
        assert len(results) == 2
        failed_results = [r for r in results if r.status == NotificationStatus.FAILED]
        success_results = [r for r in results if r.status == NotificationStatus.SENT]
        assert len(failed_results) == 1
        assert len(success_results) == 1

    def test_send_stops_after_first_success(
        self,
        notification_factory,
        notification_result_factory,
    ):
        """Test dispatcher stops trying channels after first success."""
        notification = notification_factory(channels=["chat", "email"])

        # Mock chat channel that succeeds
        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"
        mock_chat.send.return_value = [
            notification_result_factory(
                channel="chat",
                status=NotificationStatus.SENT,
            )
        ]

        # Mock email channel (should not be called)
        mock_email = MagicMock()
        mock_email.channel_name = "email"

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_chat, "email": mock_email}
        )
        results = dispatcher.send(notification)

        # Only chat should be called
        mock_chat.send.assert_called_once()
        mock_email.send.assert_not_called()

        # Only 1 result (successful chat)
        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT
        assert results[0].channel == "chat"

    def test_send_with_unknown_channel(
        self,
        mock_notification_channel,
        notification_factory,
    ):
        """Test behavior when notification specifies unknown channel."""
        notification = notification_factory(channels=["unknown"])

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel}
        )
        # Should return empty results (no channels available)
        assert len(dispatcher.send(notification)) == 0
        mock_notification_channel.send.assert_not_called()

    def test_send_with_channel_exception(
        self,
        notification_factory,
        notification_result_factory,
    ):
        """Test handling of channel exceptions."""
        notification = notification_factory(channels=["chat"])

        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"
        mock_chat.send.side_effect = Exception("API connection failed")

        dispatcher = NotificationDispatcher(channels={"chat": mock_chat})
        results = dispatcher.send(notification)

        # Should return failure result
        assert len(results) == 1
        assert results[0].status == NotificationStatus.FAILED
        assert "API connection failed" in results[0].message
        assert results[0].error_code == "CHANNEL_EXCEPTION"

    def test_send_respects_recipient_preferred_channels(
        self,
        notification_factory,
        recipient_factory,
        notification_result_factory,
    ):
        """Test recipient's preferred channels are tried first."""
        recipient = recipient_factory(
            email="user@example.com",
            preferred_channels=["email"],
        )
        notification = notification_factory(
            recipients=[recipient],
            channels=["chat", "email"],
        )

        # Mock email channel that succeeds
        mock_email = MagicMock()
        mock_email.channel_name = "email"
        mock_email.send.return_value = [
            notification_result_factory(
                channel="email",
                status=NotificationStatus.SENT,
            )
        ]

        # Mock chat channel (should not be called)
        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_chat, "email": mock_email}
        )
        results = dispatcher.send(notification)

        # Email should be tried first and succeed
        mock_email.send.assert_called_once()
        mock_chat.send.assert_not_called()
        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT
        assert results[0].channel == "email"


@pytest.mark.unit
class TestNotificationDispatcherIdempotency:
    """Tests for idempotency cache integration."""

    def test_send_with_cached_result(
        self,
        mock_notification_channel,
        notification_factory,
        notification_result_factory,
    ):
        """Test cached notification is not sent again."""
        notification = notification_factory(
            idempotency_key="test-key-123",
            channels=["chat"],
        )

        # Mock cache with existing result
        mock_cache = MagicMock()
        cached_result = notification_result_factory(status=NotificationStatus.SENT)
        # Cache returns serialized dicts (as DynamoDB would), not Pydantic objects
        mock_cache.get.return_value = {
            "results": [cached_result.model_dump(mode="json")],
            "sent_at": "2025-12-08T10:00:00Z",
        }

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel},
            idempotency_cache=mock_cache,
        )
        results = dispatcher.send(notification)

        # Should return cached result without calling channel
        assert len(results) == 1
        # Compare key fields since reconstructed object won't be identical
        assert results[0].channel == cached_result.channel
        assert results[0].status == cached_result.status
        assert results[0].message == cached_result.message
        mock_notification_channel.send.assert_not_called()
        mock_cache.get.assert_called_once_with("test-key-123")

    def test_send_without_cached_result(
        self,
        mock_notification_channel,
        notification_factory,
        notification_result_factory,
    ):
        """Test notification is sent when not cached."""
        notification = notification_factory(
            idempotency_key="new-key-456",
            channels=["chat"],
        )

        # Mock cache returns None (not found)
        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        expected_result = notification_result_factory(status=NotificationStatus.SENT)
        mock_notification_channel.channel_name = "chat"
        mock_notification_channel.send.return_value = [expected_result]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel},
            idempotency_cache=mock_cache,
        )
        dispatcher.send(notification)

        # Should send notification and cache result
        mock_notification_channel.send.assert_called_once()
        mock_cache.set.assert_called_once()

        # Verify cache.set() was called with correct arguments
        call_args = mock_cache.set.call_args
        assert call_args[0][0] == "new-key-456"  # idempotency_key
        assert "results" in call_args[0][1]  # cache_data
        assert call_args[1]["ttl_seconds"] == 3600  # default TTL

    def test_send_without_idempotency_key(
        self,
        mock_notification_channel,
        notification_factory,
        notification_result_factory,
    ):
        """Test notification without idempotency key is always sent."""
        notification = notification_factory(
            idempotency_key=None,
            channels=["chat"],
        )

        mock_cache = MagicMock()
        expected_result = notification_result_factory(status=NotificationStatus.SENT)
        mock_notification_channel.channel_name = "chat"
        mock_notification_channel.send.return_value = [expected_result]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel},
            idempotency_cache=mock_cache,
        )
        dispatcher.send(notification)

        # Should send without checking cache
        mock_notification_channel.send.assert_called_once()
        mock_cache.get.assert_not_called()
        mock_cache.set.assert_not_called()

    def test_send_cache_error_does_not_prevent_send(
        self,
        mock_notification_channel,
        notification_factory,
        notification_result_factory,
    ):
        """Test cache errors don't prevent notification delivery."""
        notification = notification_factory(
            idempotency_key="error-key",
            channels=["chat"],
        )

        # Mock cache that raises exception
        mock_cache = MagicMock()
        mock_cache.get.side_effect = Exception("Cache connection failed")

        expected_result = notification_result_factory(status=NotificationStatus.SENT)
        mock_notification_channel.channel_name = "chat"
        mock_notification_channel.send.return_value = [expected_result]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel},
            idempotency_cache=mock_cache,
        )
        results = dispatcher.send(notification)

        # Should still send notification despite cache error
        mock_notification_channel.send.assert_called_once()
        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT


@pytest.mark.unit
class TestNotificationDispatcherBroadcast:
    """Tests for broadcast() method."""

    def test_broadcast_to_all_channels(
        self,
        notification_factory,
        notification_result_factory,
    ):
        """Test broadcast sends to all channels simultaneously."""
        notification = notification_factory(channels=["chat"])

        # Create multiple mock channels
        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"
        mock_chat.send.return_value = [
            notification_result_factory(
                channel="chat",
                status=NotificationStatus.SENT,
            )
        ]

        mock_email = MagicMock()
        mock_email.channel_name = "email"
        mock_email.send.return_value = [
            notification_result_factory(
                channel="email",
                status=NotificationStatus.SENT,
            )
        ]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_chat, "email": mock_email}
        )
        results = dispatcher.broadcast(notification, all_channels=True)

        # Both channels should be called
        mock_chat.send.assert_called_once()
        mock_email.send.assert_called_once()

        # Should have 2 results
        assert len(results) == 2

    def test_broadcast_to_specified_channels(
        self,
        notification_factory,
        notification_result_factory,
    ):
        """Test broadcast respects notification.channels when all_channels=False."""
        notification = notification_factory(channels=["chat"])

        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"
        mock_chat.send.return_value = [
            notification_result_factory(
                channel="chat",
                status=NotificationStatus.SENT,
            )
        ]

        mock_email = MagicMock()
        mock_email.channel_name = "email"

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_chat, "email": mock_email}
        )
        dispatcher.broadcast(notification, all_channels=False)

        # Only chat should be called
        mock_chat.send.assert_called_once()
        mock_email.send.assert_not_called()

    def test_broadcast_handles_channel_exception(
        self,
        notification_factory,
        notification_result_factory,
    ):
        """Test broadcast continues after channel exception."""
        notification = notification_factory(channels=["chat", "email"])

        # Chat channel raises exception
        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"
        mock_chat.send.side_effect = Exception("Chat API failed")

        # Email channel succeeds
        mock_email = MagicMock()
        mock_email.channel_name = "email"
        mock_email.send.return_value = [
            notification_result_factory(
                channel="email",
                status=NotificationStatus.SENT,
            )
        ]

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_chat, "email": mock_email}
        )
        results = dispatcher.broadcast(notification)

        # Both channels should be attempted
        mock_chat.send.assert_called_once()
        mock_email.send.assert_called_once()

        # Should have failure result for chat and success for email
        assert len(results) == 2
        failed = [r for r in results if r.status == NotificationStatus.FAILED]
        success = [r for r in results if r.status == NotificationStatus.SENT]
        assert len(failed) == 1
        assert len(success) == 1


@pytest.mark.unit
class TestNotificationDispatcherHealthCheck:
    """Tests for health_check() method."""

    def test_health_check_all_channels_healthy(self, mock_notification_channel):
        """Test health check when all channels are healthy."""
        from infrastructure.operations import OperationResult

        mock_notification_channel.channel_name = "chat"
        mock_notification_channel.health_check.return_value = OperationResult.success()

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_notification_channel}
        )
        health = dispatcher.health_check()

        assert health == {"chat": True}
        mock_notification_channel.health_check.assert_called_once()

    def test_health_check_with_unhealthy_channel(self):
        """Test health check when channel is unhealthy."""
        mock_channel = MagicMock()
        mock_channel.channel_name = "chat"
        mock_channel.health_check.return_value = OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message="Slack API unreachable",
        )

        dispatcher = NotificationDispatcher(channels={"chat": mock_channel})
        health = dispatcher.health_check()

        assert health == {"chat": False}

    def test_health_check_handles_exception(self):
        """Test health check handles channel exceptions."""
        mock_channel = MagicMock()
        mock_channel.channel_name = "chat"
        mock_channel.health_check.side_effect = Exception("Health check failed")

        dispatcher = NotificationDispatcher(channels={"chat": mock_channel})
        health = dispatcher.health_check()

        # Should mark as unhealthy
        assert health == {"chat": False}

    def test_health_check_multiple_channels(self):
        """Test health check with multiple channels in mixed states."""
        mock_chat = MagicMock()
        mock_chat.channel_name = "chat"
        mock_chat.health_check.return_value = OperationResult.success()

        mock_email = MagicMock()
        mock_email.channel_name = "email"
        mock_email.health_check.return_value = OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message="Gmail API down",
        )

        dispatcher = NotificationDispatcher(
            channels={"chat": mock_chat, "email": mock_email}
        )
        health = dispatcher.health_check()

        assert health == {"chat": True, "email": False}
