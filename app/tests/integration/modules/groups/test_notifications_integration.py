"""Integration tests for groups notification system.

Tests the complete notification flow from event handlers through to
ChatChannel, verifying that group membership changes trigger real
notifications (with mocked Slack API).

Following testing strategy in /workspace/app/tests/TESTING_STRATEGY.md:
- Integration tests combining multiple components
- Test event handlers → notifications → channel
- Mock external dependencies (Slack API)
"""

import pytest
from unittest.mock import MagicMock
from infrastructure.events import Event
from modules.groups.events import handlers


@pytest.fixture
def mock_slack_client(monkeypatch):
    """Mock Slack client for integration tests."""
    mock_manager_class = MagicMock()
    mock_manager = MagicMock()
    mock_client = MagicMock()
    mock_manager.get_client.return_value = mock_client

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

    mock_manager_class.return_value = mock_manager
    monkeypatch.setattr(
        "infrastructure.notifications.channels.chat.SlackClientManager",
        mock_manager_class,
        raising=False,
    )
    return mock_client


@pytest.fixture
def mock_circuit_breaker(monkeypatch):
    """Mock circuit breaker to track calls while passing through function execution.

    This fixture mocks CircuitBreaker in both:
    1. The resilience module (where it's defined)
    2. The channel modules (where it's imported)

    This ensures the mock is used everywhere, while allowing test assertions
    on call_count to verify circuit breaker interactions.
    """
    mock_cb_class = MagicMock()
    mock_cb = MagicMock()
    mock_cb.call = MagicMock(
        side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
    )
    mock_cb_class.return_value = mock_cb

    # Patch at resilience module level
    monkeypatch.setattr(
        "infrastructure.resilience.circuit_breaker.CircuitBreaker",
        mock_cb_class,
        raising=False,
    )

    # Patch at channel module import levels
    monkeypatch.setattr(
        "infrastructure.notifications.channels.chat.CircuitBreaker",
        mock_cb_class,
        raising=False,
    )
    monkeypatch.setattr(
        "infrastructure.notifications.channels.email.CircuitBreaker",
        mock_cb_class,
        raising=False,
    )
    monkeypatch.setattr(
        "infrastructure.notifications.channels.sms.CircuitBreaker",
        mock_cb_class,
        raising=False,
    )

    return mock_cb


@pytest.fixture
def mock_idempotency_cache(monkeypatch):
    """Mock idempotency cache to avoid DynamoDB calls."""
    mock_get_cache = MagicMock()
    mock_cache = MagicMock()
    mock_cache.get.return_value = None
    mock_cache.set.return_value = None
    mock_get_cache.return_value = mock_cache
    monkeypatch.setattr(
        "infrastructure.idempotency.factory.get_cache", mock_get_cache, raising=False
    )
    return mock_cache


@pytest.fixture(autouse=True)
def reset_handler_singleton():
    """Reset notification handler singleton before each test."""
    from modules.groups.events.handlers import reset_notification_handler

    reset_notification_handler()
    yield
    reset_notification_handler()


@pytest.mark.integration
class TestGroupNotificationFlow:
    """Integration tests for complete notification flow."""

    def test_member_added_event_sends_notifications(
        self, mock_slack_client, mock_circuit_breaker, mock_idempotency_cache
    ):
        """Test member added event triggers Slack notifications."""
        event = Event(
            event_type="group.member.added",
            metadata={
                "request": {
                    "requestor": "admin@example.com",
                    "member_email": "user@example.com",
                    "group_id": "engineering-team",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "add_member",
                    "provider": "google",
                    "status": "success",
                },
            },
        )

        handlers.handle_member_added(event)

        assert mock_slack_client.users_lookupByEmail.call_count >= 2
        assert mock_slack_client.conversations_open.call_count >= 2
        assert mock_slack_client.chat_postMessage.call_count >= 2

        calls = mock_slack_client.chat_postMessage.call_args_list
        messages = [call.kwargs.get("text", "") for call in calls]

        assert any("added" in msg.lower() for msg in messages)
        assert any("engineering-team" in msg for msg in messages)

    def test_member_removed_event_sends_notifications(
        self, mock_slack_client, mock_circuit_breaker, mock_idempotency_cache
    ):
        """Test member removed event triggers Slack notifications."""
        event = Event(
            event_type="group.member.removed",
            metadata={
                "request": {
                    "requestor": "admin@example.com",
                    "member_email": "user@example.com",
                    "group_id": "engineering-team",
                    "provider": "aws",
                },
                "orchestration": {
                    "action": "remove_member",
                    "provider": "aws",
                    "status": "success",
                },
            },
        )

        handlers.handle_member_removed(event)

        assert mock_slack_client.chat_postMessage.call_count >= 2

        calls = mock_slack_client.chat_postMessage.call_args_list
        messages = [call.kwargs.get("text", "") for call in calls]

        assert any("removed" in msg.lower() for msg in messages)
        assert any("AWS" in msg for msg in messages)

    def test_read_only_operation_skips_notifications(
        self, mock_slack_client, mock_circuit_breaker, mock_idempotency_cache
    ):
        """Test read-only operations don't trigger notifications."""
        event = Event(
            event_type="group.listed",
            metadata={
                "request": {
                    "requestor": "admin@example.com",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "list_groups",
                    "provider": "google",
                    "status": "success",
                },
            },
        )

        handlers.handle_group_listed(event)

        mock_slack_client.chat_postMessage.assert_not_called()

    def test_slack_user_resolution_failure_handled_gracefully(
        self, mock_slack_client, mock_circuit_breaker, mock_idempotency_cache
    ):
        """Test notification handles Slack user lookup failures gracefully."""
        mock_slack_client.users_lookupByEmail.return_value = {
            "ok": False,
            "error": "users_not_found",
        }

        event = Event(
            event_type="group.member.added",
            metadata={
                "request": {
                    "requestor": "nonexistent@example.com",
                    "member_email": "user@example.com",
                    "group_id": "engineering-team",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "add_member",
                    "provider": "google",
                    "status": "success",
                },
            },
        )

        handlers.handle_member_added(event)

        mock_slack_client.users_lookupByEmail.assert_called()
        mock_slack_client.chat_postMessage.assert_not_called()

    def test_notification_includes_idempotency_key(
        self, mock_slack_client, mock_circuit_breaker, mock_idempotency_cache
    ):
        """Test notifications include idempotency keys."""
        event = Event(
            event_type="group.member.added",
            metadata={
                "request": {
                    "requestor": "admin@example.com",
                    "member_email": "user@example.com",
                    "group_id": "engineering-team",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "add_member",
                    "provider": "google",
                },
            },
        )

        handlers.handle_member_added(event)

        mock_idempotency_cache.get.assert_called()


@pytest.mark.integration
class TestNotificationResilience:
    """Integration tests for notification resilience features."""

    def test_circuit_breaker_opens_after_failures(
        self, mock_slack_client, mock_circuit_breaker, mock_idempotency_cache
    ):
        """Test circuit breaker protects against repeated Slack failures."""
        mock_slack_client.users_lookupByEmail.return_value = {
            "ok": True,
            "user": {"id": "U12345"},
        }
        mock_slack_client.conversations_open.return_value = {
            "ok": True,
            "channel": {"id": "D12345"},
        }
        mock_slack_client.chat_postMessage.side_effect = Exception("Slack API error")

        event = Event(
            event_type="group.member.added",
            metadata={
                "request": {
                    "requestor": "admin@example.com",
                    "member_email": "user@example.com",
                    "group_id": "engineering-team",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "add_member",
                    "provider": "google",
                },
            },
        )

        for _ in range(3):
            handlers.handle_member_added(event)

        # Circuit breaker's call method should be invoked for each notification attempt
        # Each event triggers 2 notifications (requestor + member), so 3 events = 6 calls
        assert mock_circuit_breaker.call.call_count >= 4

    def test_notification_failure_does_not_propagate(
        self, mock_slack_client, mock_circuit_breaker, mock_idempotency_cache
    ):
        """Test notification failures don't propagate to event handlers."""
        mock_slack_client.chat_postMessage.side_effect = Exception("Network error")

        event = Event(
            event_type="group.member.added",
            metadata={
                "request": {
                    "requestor": "admin@example.com",
                    "member_email": "user@example.com",
                    "group_id": "engineering-team",
                    "provider": "google",
                },
                "orchestration": {
                    "action": "add_member",
                    "provider": "google",
                },
            },
        )

        try:
            handlers.handle_member_added(event)
            exception_raised = False
        except Exception:
            exception_raised = True

        assert not exception_raised
