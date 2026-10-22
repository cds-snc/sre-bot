"""Fixtures for infrastructure.logging tests."""

from unittest.mock import Mock

import pytest

from contracts.configuration import HostInfo


@pytest.fixture
def mock_settings():
    """Mock HostInfo instance for testing."""
    settings = Mock(spec=HostInfo)
    settings.environment = "local"
    return settings
