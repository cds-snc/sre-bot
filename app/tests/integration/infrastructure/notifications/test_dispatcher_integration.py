"""Integration tests for NotificationDispatcher.

Tests end-to-end notification flows with real channel implementations
(using mocked external APIs).

Tests cover:
- End-to-end notification flow through multiple channels
- Idempotency cache integration
- Circuit breaker behavior
- Channel fallback scenarios
- Multi-recipient handling
"""

import pytest
from unittest.mock import MagicMock, patch

from infrastructure.notifications.dispatcher import NotificationDispatcher
from infrastructure.notifications.channels.chat import ChatChannel
from infrastructure.notifications.channels.email import EmailChannel
from infrastructure.notifications.channels.sms import SMSChannel
from infrastructure.notifications.models import (
    Notification,
    Recipient,
    NotificationStatus,
)
from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus


class MockIdempotencyCache(IdempotencyCache):
    """In-memory idempotency cache for testing."""

    def __init__(self):
        self._cache = {}

    def get(self, key: str):
        return self._cache.get(key)

    def set(self, key: str, response, ttl_seconds: int):
        self._cache[key] = response

    def clear(self):
        self._cache.clear()

    def get_stats(self):
        return {"size": len(self._cache)}


@pytest.mark.integration
class TestDispatcherWithRealChannels:
    """Integration tests with real channel implementations."""

    @pytest.fixture
    def mock_slack_client(self):
        """Mock Slack client for ChatChannel."""
        with patch(
            "infrastructure.notifications.channels.chat.SlackClientManager"
        ) as mock_manager:
            mock_client = MagicMock()
            mock_manager.return_value.get_client.return_value = mock_client

            # Mock successful user lookup
            mock_client.users_lookupByEmail.return_value = {
                "ok": True,
                "user": {"id": "U12345"},
            }

            # Mock successful DM
            mock_client.conversations_open.return_value = {
                "ok": True,
                "channel": {"id": "D12345"},
            }
            mock_client.chat_postMessage.return_value = {
                "ok": True,
                "ts": "1234567890.123456",
            }

            yield mock_client

    @pytest.fixture
    def mock_gmail_service(self):
        """Mock Gmail service for EmailChannel."""
        with patch.multiple(
            "infrastructure.notifications.channels.email.gmail_next",
            send_email=MagicMock(
                return_value=OperationResult(
                    status=OperationStatus.SUCCESS,
                    message="Email sent successfully",
                    data={"id": "msg123", "threadId": "thread123"},
                )
            ),
            list_messages=MagicMock(
                return_value=OperationResult(
                    status=OperationStatus.SUCCESS,
                    message="Messages listed successfully",
                    data=[],
                )
            ),
        ) as mocks:
            yield mocks

    @pytest.fixture
    def mock_notify_client(self):
        """Mock GC Notify client for SMSChannel."""
        with patch(
            "infrastructure.notifications.channels.sms.post_event"
        ) as mock_post_event:
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": "sms123"}
            mock_post_event.return_value = mock_response
            yield mock_post_event

    def test_send_notification_through_chat_channel(self, mock_slack_client):
        """Test end-to-end chat notification."""
        chat_channel = ChatChannel()
        dispatcher = NotificationDispatcher(channels={"chat": chat_channel})

        notification = Notification(
            subject="Test Notification",
            message="This is a test message",
            recipients=[Recipient(email="user@example.com")],
            channels=["chat"],
        )

        results = dispatcher.send(notification)

        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT
        assert results[0].channel == "chat"
        assert results[0].external_id is not None

        # Verify Slack API calls
        mock_slack_client.users_lookupByEmail.assert_called_once_with(
            email="user@example.com"
        )
        mock_slack_client.conversations_open.assert_called_once()
        mock_slack_client.chat_postMessage.assert_called_once()

    def test_send_notification_through_email_channel(self, mock_gmail_service):
        """Test end-to-end email notification."""
        email_channel = EmailChannel()
        dispatcher = NotificationDispatcher(channels={"email": email_channel})

        notification = Notification(
            subject="Test Email",
            message="This is a test email message",
            recipients=[Recipient(email="user@example.com")],
            channels=["email"],
        )

        results = dispatcher.send(notification)

        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT
        assert results[0].channel == "email"
        assert results[0].external_id is not None

    def test_send_notification_through_sms_channel(self, mock_notify_client):
        """Test end-to-end SMS notification."""
        sms_channel = SMSChannel()
        dispatcher = NotificationDispatcher(channels={"sms": sms_channel})

        notification = Notification(
            subject="Test SMS",
            message="This is a test SMS message",
            recipients=[
                Recipient(email="user@example.com", phone_number="+15551234567")
            ],
            channels=["sms"],
        )

        results = dispatcher.send(notification)

        assert len(results) == 1
        assert results[0].status == NotificationStatus.SENT
        assert results[0].channel == "sms"
        assert results[0].external_id is not None

        # Verify Notify API calls
        mock_notify_client.assert_called_once()

    def test_multi_channel_fallback(self, mock_slack_client, mock_gmail_service):
        """Test fallback from chat to email when chat fails."""
        # Configure Slack to fail
        mock_slack_client.users_lookupByEmail.side_effect = Exception("Slack API error")

        chat_channel = ChatChannel()
        email_channel = EmailChannel()

        dispatcher = NotificationDispatcher(
            channels={"chat": chat_channel, "email": email_channel},
            fallback_order=["chat", "email"],
        )

        notification = Notification(
            subject="Test Fallback",
            message="Testing fallback behavior",
            recipients=[Recipient(email="user@example.com")],
            channels=["chat", "email"],
        )

        results = dispatcher.send(notification)

        # Should have 2 results: 1 failed chat, 1 successful email
        assert len(results) == 2

        failed_results = [r for r in results if r.status == NotificationStatus.FAILED]
        success_results = [r for r in results if r.status == NotificationStatus.SENT]

        assert len(failed_results) == 1
        assert failed_results[0].channel == "chat"

        assert len(success_results) == 1
        assert success_results[0].channel == "email"

    def test_multi_recipient_notification(self, mock_slack_client):
        """Test notification to multiple recipients."""
        chat_channel = ChatChannel()
        dispatcher = NotificationDispatcher(channels={"chat": chat_channel})

        # Mock user lookups for multiple users
        def mock_lookup(email):
            user_ids = {
                "user1@example.com": "U11111",
                "user2@example.com": "U22222",
                "user3@example.com": "U33333",
            }
            return {"ok": True, "user": {"id": user_ids.get(email, "U99999")}}

        mock_slack_client.users_lookupByEmail.side_effect = mock_lookup

        notification = Notification(
            subject="Team Update",
            message="Important team notification",
            recipients=[
                Recipient(email="user1@example.com"),
                Recipient(email="user2@example.com"),
                Recipient(email="user3@example.com"),
            ],
            channels=["chat"],
        )

        results = dispatcher.send(notification)

        # Should have 3 results, one per recipient
        assert len(results) == 3
        assert all(r.status == NotificationStatus.SENT for r in results)

        # Verify all users were looked up
        assert mock_slack_client.users_lookupByEmail.call_count == 3


@pytest.mark.integration
class TestDispatcherIdempotencyIntegration:
    """Integration tests for idempotency cache behavior."""

    @pytest.fixture
    def idempotency_cache(self):
        """Create in-memory idempotency cache."""
        return MockIdempotencyCache()

    @pytest.fixture
    def mock_slack_client(self):
        """Mock Slack client for testing."""
        with patch(
            "infrastructure.notifications.channels.chat.SlackClientManager"
        ) as mock_manager:
            mock_client = MagicMock()
            mock_manager.return_value.get_client.return_value = mock_client

            mock_client.users_lookupByEmail.return_value = {
                "ok": True,
                "user": {"id": "U12345"},
            }
            mock_client.conversations_open.return_value = {
                "ok": True,
                "channel": {"id": "D12345"},
            }
            mock_client.chat_postMessage.return_value = {
                "ok": True,
                "ts": "1234567890.123456",
            }

            yield mock_client

    def test_duplicate_notification_prevented(
        self, idempotency_cache, mock_slack_client
    ):
        """Test idempotency prevents duplicate sends."""
        chat_channel = ChatChannel()
        dispatcher = NotificationDispatcher(
            channels={"chat": chat_channel},
            idempotency_cache=idempotency_cache,
        )

        notification = Notification(
            subject="Test Notification",
            message="This should only be sent once",
            recipients=[Recipient(email="user@example.com")],
            channels=["chat"],
            idempotency_key="unique-operation-123",
        )

        # Send first time
        results1 = dispatcher.send(notification)
        assert len(results1) == 1
        assert results1[0].status == NotificationStatus.SENT

        # Verify Slack API was called
        assert mock_slack_client.chat_postMessage.call_count == 1

        # Send second time with same idempotency key
        results2 = dispatcher.send(notification)
        assert len(results2) == 1
        assert results2[0].status == NotificationStatus.SENT

        # Verify Slack API was NOT called again
        assert mock_slack_client.chat_postMessage.call_count == 1

        # Verify cached results are returned
        assert results1[0].external_id == results2[0].external_id

    def test_different_idempotency_keys_send_separately(
        self, idempotency_cache, mock_slack_client
    ):
        """Test different idempotency keys allow separate sends."""
        chat_channel = ChatChannel()
        dispatcher = NotificationDispatcher(
            channels={"chat": chat_channel},
            idempotency_cache=idempotency_cache,
        )

        notification1 = Notification(
            subject="First Notification",
            message="First message",
            recipients=[Recipient(email="user@example.com")],
            channels=["chat"],
            idempotency_key="operation-1",
        )

        notification2 = Notification(
            subject="Second Notification",
            message="Second message",
            recipients=[Recipient(email="user@example.com")],
            channels=["chat"],
            idempotency_key="operation-2",
        )

        # Send both notifications
        results1 = dispatcher.send(notification1)
        results2 = dispatcher.send(notification2)

        # Both should succeed
        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].status == NotificationStatus.SENT
        assert results2[0].status == NotificationStatus.SENT

        # Verify both were sent (2 API calls)
        assert mock_slack_client.chat_postMessage.call_count == 2

    def test_cache_stats_tracking(self, idempotency_cache, mock_slack_client):
        """Test idempotency cache statistics."""
        chat_channel = ChatChannel()
        dispatcher = NotificationDispatcher(
            channels={"chat": chat_channel},
            idempotency_cache=idempotency_cache,
        )

        # Send multiple unique notifications
        for i in range(3):
            notification = Notification(
                subject=f"Notification {i}",
                message=f"Message {i}",
                recipients=[Recipient(email="user@example.com")],
                channels=["chat"],
                idempotency_key=f"operation-{i}",
            )
            dispatcher.send(notification)

        # Check cache stats
        stats = idempotency_cache.get_stats()
        assert stats["size"] == 3


@pytest.mark.integration
class TestDispatcherHealthCheck:
    """Integration tests for health check functionality."""

    @pytest.fixture
    def mock_slack_client(self):
        """Mock Slack client."""
        with patch(
            "infrastructure.notifications.channels.chat.SlackClientManager"
        ) as mock_manager:
            mock_client = MagicMock()
            mock_manager.return_value.get_client.return_value = mock_client
            mock_client.auth_test.return_value = {"ok": True}
            yield mock_client

    @pytest.fixture
    def mock_gmail_service(self):
        """Mock Gmail service."""
        with patch.multiple(
            "infrastructure.notifications.channels.email.gmail_next",
            send_email=MagicMock(
                return_value=OperationResult(
                    status=OperationStatus.SUCCESS,
                    message="Email sent successfully",
                    data={"id": "msg123", "threadId": "thread123"},
                )
            ),
            list_messages=MagicMock(
                return_value=OperationResult(
                    status=OperationStatus.SUCCESS,
                    message="Messages listed successfully",
                    data=[],
                )
            ),
        ) as mocks:
            yield mocks

    def test_health_check_all_channels(self, mock_slack_client, mock_gmail_service):
        """Test health check across multiple channels."""
        chat_channel = ChatChannel()
        email_channel = EmailChannel()

        dispatcher = NotificationDispatcher(
            channels={"chat": chat_channel, "email": email_channel}
        )

        health = dispatcher.health_check()

        assert health == {"chat": True, "email": True}

    def test_health_check_with_failing_channel(
        self, mock_slack_client, mock_gmail_service
    ):
        """Test health check when one channel fails."""
        # Configure Slack to fail
        mock_slack_client.auth_test.side_effect = Exception("Auth failed")

        chat_channel = ChatChannel()
        email_channel = EmailChannel()

        dispatcher = NotificationDispatcher(
            channels={"chat": chat_channel, "email": email_channel}
        )

        health = dispatcher.health_check()

        assert health == {"chat": False, "email": True}
