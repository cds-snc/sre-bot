"""Fixtures for integration.infrastructure.notifications tests."""

import pytest
from unittest.mock import Mock

from infrastructure.configuration import Settings


@pytest.fixture
def mock_settings():
    """Mock Settings instance for testing."""
    settings = Mock(spec=Settings)
    settings.LOG_LEVEL = "INFO"
    settings.google_workspace = Mock()
    settings.google_workspace.GOOGLE_DELEGATED_ADMIN_EMAIL = "test-email@example.com"
    settings.is_production = False
    settings.notify = Mock()
    settings.notify.NOTIFY_API_KEY = "test-key"
    settings.notify.NOTIFY_API_URL = "https://api.example.com"
    return settings
