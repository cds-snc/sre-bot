"""Module-level fixtures for infrastructure tests (Level 2)."""

from unittest.mock import Mock

import pytest

from infrastructure.configuration import AppSettings


@pytest.fixture
def mock_settings():
    """Mock Settings instance for testing."""
    settings = Mock(spec=AppSettings)
    settings.LOG_LEVEL = "INFO"
    settings.ENVIRONMENT = "local"
    return settings


# Note: Command-framework-specific fixtures are in Level 3 conftest
# (tests/unit/infrastructure/commands/conftest.py)
