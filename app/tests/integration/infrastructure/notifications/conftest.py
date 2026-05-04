"""Fixtures for integration.infrastructure.notifications tests."""

import pytest
from unittest.mock import Mock, MagicMock

from infrastructure.configuration.integrations.google import (
    GoogleWorkspaceSettings,
)
from infrastructure.configuration.integrations.notify import NotifySettings


@pytest.fixture(autouse=True)
def mock_circuit_breaker(monkeypatch):
    """Mock CircuitBreaker for all notification tests.

    This fixture automatically patches CircuitBreaker across all test modules
    to prevent runtime initialization errors during testing. The mock's call()
    method is configured to execute the passed function directly (bypass pattern).

    This is autouse because tests in this module don't have their own
    mock_circuit_breaker fixture that they depend on testing.
    """

    def mock_call(func, *args, **kwargs):
        """Mock implementation of circuit_breaker.call() that executes the function."""
        return func(*args, **kwargs)

    mock_breaker = MagicMock()
    mock_breaker.call = MagicMock(side_effect=mock_call)

    # Patch CircuitBreaker at all import locations
    mock_cb_class = MagicMock(return_value=mock_breaker)
    monkeypatch.setattr(
        "infrastructure.notifications.channels.chat.CircuitBreaker",
        mock_cb_class,
    )
    monkeypatch.setattr(
        "infrastructure.notifications.channels.email.CircuitBreaker",
        mock_cb_class,
    )
    monkeypatch.setattr(
        "infrastructure.notifications.channels.sms.CircuitBreaker",
        mock_cb_class,
    )

    return mock_breaker


@pytest.fixture
def mock_settings():
    """Mock GoogleWorkspaceSettings for EmailChannel."""
    settings = Mock(spec=GoogleWorkspaceSettings)
    settings.GOOGLE_DELEGATED_ADMIN_EMAIL = "test-email@example.com"
    return settings


@pytest.fixture
def mock_notify_settings():
    """Mock NotifySettings for SMSChannel."""
    settings = Mock(spec=NotifySettings)
    settings.NOTIFY_API_KEY = "test-key"
    settings.NOTIFY_API_URL = "https://api.example.com"
    return settings
