"""Test fixtures for notification infrastructure tests."""

import pytest
from typing import Optional, List, Dict, Any
from unittest.mock import MagicMock

from infrastructure.notifications.models import (
    Notification,
    Recipient,
    NotificationPriority,
    NotificationStatus,
    NotificationResult,
)


@pytest.fixture
def mock_settings():
    """Mock Settings instance for testing channels.

    Returns:
        Mock settings with notify and google_workspace configurations
    """
    mock = MagicMock()
    mock.notify.NOTIFY_API_KEY = "test-api-key"
    mock.notify.NOTIFY_API_URL = "https://api.notification.canada.ca"
    mock.google_workspace.GOOGLE_DELEGATED_ADMIN_EMAIL = "admin@example.com"
    return mock


@pytest.fixture
def recipient_factory():
    """Factory for creating Recipient instances.

    Returns:
        Factory function that creates Recipient objects with customizable fields

    Example:
        recipient = recipient_factory(email="test@example.com")
        recipient_with_slack = recipient_factory(
            email="user@example.com",
            slack_user_id="U12345"
        )
    """

    def _factory(
        email: str = "test@example.com",
        slack_user_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        preferred_channels: Optional[List[str]] = None,
    ) -> Recipient:
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
        recipient_factory: Fixture for creating recipients

    Returns:
        Factory function that creates Notification objects with customizable fields

    Example:
        notification = notification_factory(subject="Test", message="Test message")
        multi_channel = notification_factory(
            channels=["chat", "email"],
            priority=NotificationPriority.URGENT
        )
    """

    def _factory(
        subject: str = "Test Notification",
        message: str = "Test message body",
        recipients: Optional[List[Recipient]] = None,
        channels: Optional[List[str]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        idempotency_key: Optional[str] = None,
        html_body: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        if recipients is None:
            recipients = [recipient_factory()]

        return Notification(
            subject=subject,
            message=message,
            recipients=recipients,
            channels=channels or ["chat"],
            priority=priority,
            idempotency_key=idempotency_key,
            html_body=html_body,
            metadata=metadata or {},
        )

    return _factory


@pytest.fixture
def notification_result_factory(notification_factory):
    """Factory for creating NotificationResult instances.

    Args:
        notification_factory: Fixture for creating notifications

    Returns:
        Factory function that creates NotificationResult objects

    Example:
        result = notification_result_factory(status=NotificationStatus.SENT)
        failed = notification_result_factory(
            status=NotificationStatus.FAILED,
            error_code="API_ERROR"
        )
    """

    def _factory(
        notification: Optional[Notification] = None,
        channel: str = "chat",
        status: NotificationStatus = NotificationStatus.SENT,
        message: str = "Success",
        error_code: Optional[str] = None,
        external_id: Optional[str] = None,
    ) -> NotificationResult:
        if notification is None:
            notification = notification_factory()

        return NotificationResult(
            notification=notification,
            channel=channel,
            status=status,
            message=message,
            error_code=error_code,
            external_id=external_id,
        )

    return _factory


@pytest.fixture
def mock_notification_channel():
    """Mock NotificationChannel for testing.

    Returns:
        MagicMock with channel_name, send, resolve_recipient, and health_check methods

    Example:
        def test_with_mock_channel(mock_notification_channel):
            mock_notification_channel.send.return_value = [
                NotificationResult(...)
            ]
            results = mock_notification_channel.send(notification)
    """
    from infrastructure.operations import OperationResult

    channel = MagicMock()
    channel.channel_name = "mock"
    channel.send.return_value = []
    channel.resolve_recipient.return_value = OperationResult.success(
        data={"user_id": "U123"}, message="Recipient resolved"
    )
    channel.health_check.return_value = OperationResult.success(
        message="Channel healthy"
    )
    return channel
