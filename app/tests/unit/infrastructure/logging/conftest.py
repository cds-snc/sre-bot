"""Fixtures for infrastructure.logging tests."""

import pytest
from unittest.mock import Mock

from infrastructure.configuration import Settings


@pytest.fixture
def mock_settings():
    """Mock Settings instance for testing."""
    settings = Mock(spec=Settings)
    settings.LOG_LEVEL = "INFO"
    settings.is_production = False
    return settings
