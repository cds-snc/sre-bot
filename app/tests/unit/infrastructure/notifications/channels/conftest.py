"""Feature-level fixtures for notification channel tests (Level 4)."""

from unittest.mock import MagicMock, Mock
import pytest

from infrastructure.notifications.models import (
    Notification,
    Recipient,
    NotificationPriority,
)
from infrastructure.operations import OperationResult


@pytest.fixture
def mock_circuit_breaker():
    """Mock CircuitBreaker that always allows calls through.

    Returns:
        MagicMock CircuitBreaker that executes functions normally
    """
    breaker = MagicMock()
    breaker.failure_count = 0
    breaker.state = "CLOSED"

    # Mock call method to execute function normally
    def call_side_effect(func, *args, **kwargs):
        return func(*args, **kwargs)

    breaker.call.side_effect = call_side_effect
    return breaker


@pytest.fixture
def mock_slack_client():
    """Mock Slack WebClient for chat channel tests.

    Returns:
        MagicMock configured with successful Slack API responses
    """
    client = MagicMock()

    # Mock auth_test - health check
    client.auth_test = MagicMock(
        return_value={
            "ok": True,
            "team": "Test Team",
            "user": "test_bot",
        }
    )

    # Mock users_lookupByEmail - recipient resolution
    client.users_lookupByEmail = MagicMock(
        return_value={
            "ok": True,
            "user": {
                "id": "U12345TEST",
                "profile": {"email": "test@example.com"},
            },
        }
    )

    # Mock users_info - user ID validation
    client.users_info = MagicMock(
        return_value={
            "ok": True,
            "user": {
                "id": "U12345TEST",
                "profile": {"email": "test@example.com"},
            },
        }
    )

    # Mock conversations_open - DM channel opening
    client.conversations_open = MagicMock(
        return_value={
            "ok": True,
            "channel": {"id": "D12345TEST"},
        }
    )

    # Mock chat_postMessage - message sending
    client.chat_postMessage = MagicMock(
        return_value={
            "ok": True,
            "ts": "1234567890.123456",
            "channel": "D12345TEST",
        }
    )

    return client


@pytest.fixture
def mock_slack_client_manager(mock_slack_client):
    """Mock SlackClientManager returning mock Slack client.

    Args:
        mock_slack_client: Mock Slack WebClient fixture

    Returns:
        MagicMock SlackClientManager
    """
    manager = MagicMock()
    manager.get_client = MagicMock(return_value=mock_slack_client)
    return manager


@pytest.fixture
def mock_gmail_next():
    """Mock gmail_next module for email channel unit tests.

    Returns:
        MagicMock module with send_email and list_messages methods.
        Returns OperationResult objects directly without calling real implementation.
    """
    gmail_mock = MagicMock()

    # Mock successful send_email - returns OperationResult as gmail_next.send_email() would
    gmail_mock.send_email = MagicMock(
        return_value=OperationResult.success(
            data={
                "id": "msg_12345",
                "labelIds": ["SENT"],
                "threadId": "thread_12345",
            },
            message="Email sent via Gmail",
        )
    )

    # Mock successful list_messages for health check
    gmail_mock.list_messages = MagicMock(
        return_value=OperationResult.success(
            data=[],
            message="List messages successful",
        )
    )

    return gmail_mock


@pytest.fixture
def mock_notify_post_event():
    """Mock post_event function for SMS channel tests.

    Returns:
        MagicMock returning successful GC Notify response
    """
    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.json = MagicMock(
        return_value={
            "id": "notification_12345",
            "reference": None,
            "content": {"body": "Test message"},
        }
    )

    post_event_mock = MagicMock(return_value=mock_response)
    return post_event_mock


@pytest.fixture
def sample_notification():
    """Sample Notification with all fields populated.

    Returns:
        Notification instance for testing
    """
    return Notification(
        subject="Test Notification",
        message="This is a test notification message.",
        recipients=[
            Recipient(
                email="test@example.com",
                slack_user_id="U12345TEST",
                phone_number="+15555551234",
                preferred_channels=["chat", "email"],
            )
        ],
        priority=NotificationPriority.NORMAL,
        html_body="<p>This is a test notification message.</p>",
        metadata={"test_key": "test_value"},
        channels=["chat"],
        retry_on_failure=True,
        idempotency_key="test_key_12345",
    )


@pytest.fixture
def recipient_factory():
    """Factory for creating Recipient instances.

    Returns:
        Callable that creates Recipient with default or custom values
    """

    def _factory(
        email: str = "test@example.com",
        slack_user_id: str = None,
        phone_number: str = None,
        preferred_channels: list = None,
    ):
        return Recipient(
            email=email,
            slack_user_id=slack_user_id,
            phone_number=phone_number,
            preferred_channels=preferred_channels or ["chat"],
        )

    return _factory


@pytest.fixture
def notification_factory(recipient_factory):
    """Factory for creating Notification instances.

    Args:
        recipient_factory: Recipient factory fixture

    Returns:
        Callable that creates Notification with default or custom values
    """

    def _factory(
        subject: str = "Test Subject",
        message: str = "Test message",
        recipients: list = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        html_body: str = None,
        metadata: dict = None,
        channels: list = None,
        retry_on_failure: bool = True,
        idempotency_key: str = None,
    ):
        if recipients is None:
            recipients = [recipient_factory()]

        return Notification(
            subject=subject,
            message=message,
            recipients=recipients,
            priority=priority,
            html_body=html_body,
            metadata=metadata or {},
            channels=channels or ["chat"],
            retry_on_failure=retry_on_failure,
            idempotency_key=idempotency_key,
        )

    return _factory
