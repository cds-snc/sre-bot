"""Module-level fixtures for infrastructure tests (Level 2)."""

from unittest.mock import Mock

import pytest

from contracts.configuration import HostInfo


@pytest.fixture
def mock_settings():
    """Mock HostInfo instance for testing."""
    settings = Mock(spec=HostInfo)
    settings.environment = "local"
    return settings


# Note: Command-framework-specific fixtures are in Level 3 conftest
# (tests/unit/infrastructure/commands/conftest.py)
