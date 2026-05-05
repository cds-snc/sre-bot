"""Tests for notification narrow-slice settings injection."""

from typing import Any
from unittest.mock import Mock

import pytest

from infrastructure.configuration.integrations.google import GoogleWorkspaceSettings
from infrastructure.configuration.integrations.notify import NotifySettings
from infrastructure.notifications.channels.chat import ChatChannel
from infrastructure.notifications.channels.base import NotificationChannel
from infrastructure.notifications.channels.email import EmailChannel
from infrastructure.notifications.channels.sms import SMSChannel
from infrastructure.notifications.service import NotificationService


@pytest.mark.unit
def test_email_channel_accepts_google_workspace_settings() -> None:
    """EmailChannel constructs with GoogleWorkspaceSettings slice only."""
    email_provider_settings = Mock(spec=GoogleWorkspaceSettings)
    email_provider_settings.GOOGLE_DELEGATED_ADMIN_EMAIL = "sender@example.com"

    channel = EmailChannel(email_provider_settings=email_provider_settings)

    assert channel is not None


@pytest.mark.unit
def test_email_channel_uses_delegated_admin_email() -> None:
    """EmailChannel reads sender email from narrow settings slice."""
    email_provider_settings = Mock(spec=GoogleWorkspaceSettings)
    email_provider_settings.GOOGLE_DELEGATED_ADMIN_EMAIL = "admin@example.com"

    channel = EmailChannel(email_provider_settings=email_provider_settings)

    assert channel._sender_email == "admin@example.com"


@pytest.mark.unit
def test_sms_channel_accepts_notify_settings() -> None:
    """SMSChannel constructs with NotifySettings slice only."""
    notify_settings = Mock(spec=NotifySettings)
    notify_settings.NOTIFY_API_URL = "https://api.notification.canada.ca"

    channel = SMSChannel(notify_settings=notify_settings)

    assert channel is not None


@pytest.mark.unit
def test_sms_channel_uses_notify_api_url() -> None:
    """SMSChannel reads API URL from narrow settings slice."""
    notify_settings = Mock(spec=NotifySettings)
    notify_settings.NOTIFY_API_URL = "https://api.example.com"

    channel = SMSChannel(notify_settings=notify_settings)

    assert channel._api_url == "https://api.example.com"


@pytest.mark.unit
def test_notification_service_no_settings_parameter() -> None:
    """NotificationService constructs from injected channels without settings kwarg."""
    channels: dict[str, NotificationChannel] = {"chat": ChatChannel()}

    service = NotificationService(channels=channels)

    assert service is not None


@pytest.mark.unit
def test_notification_service_rejects_legacy_settings_kwarg() -> None:
    """Legacy settings kwarg is not accepted by NotificationService."""
    kwargs: dict[str, Any] = {"channels": {"chat": ChatChannel()}, "settings": Mock()}

    with pytest.raises(TypeError):
        NotificationService(**kwargs)
