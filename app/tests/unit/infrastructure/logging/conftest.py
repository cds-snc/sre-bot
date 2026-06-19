"""Fixtures for infrastructure.logging tests."""

import pytest
from unittest.mock import Mock

from infrastructure.configuration.app import AppSettings


@pytest.fixture
def mock_settings():
    """Mock AppSettings instance for testing."""
    settings = Mock(spec=AppSettings)
    settings.LOG_LEVEL = "INFO"
    settings.is_production = False
    return settings
