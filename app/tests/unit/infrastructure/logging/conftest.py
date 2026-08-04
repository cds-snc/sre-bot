"""Fixtures for infrastructure.logging tests."""

from unittest.mock import Mock

import pytest

from infrastructure.configuration.app import AppSettings


@pytest.fixture
def mock_settings():
    """Mock AppSettings instance for testing."""
    settings = Mock(spec=AppSettings)
    settings.LOG_LEVEL = "INFO"
    settings.ENVIRONMENT = "local"
    return settings
