"""Fixtures for integration.infrastructure.notifications tests."""

import pytest
from unittest.mock import Mock, MagicMock

from infrastructure.configuration.integrations.google import (
    GoogleWorkspaceSettings,
)
from infrastructure.configuration.integrations.notify import NotifySettings


@pytest.fixture(autouse=True)
def mock_circuit_breaker():
    """Provide a mock CircuitBreaker for injection into notification channels.

    CircuitBreaker is now injected via constructor (ADR-0076 S3) rather than
    constructed inside the channel, so module-level patching is no longer needed.
    The mock's call() method executes the passed function directly (bypass pattern).
    """

    def mock_call(func, *args, **kwargs):
        return func(*args, **kwargs)

    mock_breaker = MagicMock()
    mock_breaker.call = MagicMock(side_effect=mock_call)
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
