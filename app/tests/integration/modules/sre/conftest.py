"""Integration test fixtures for SRE module.

Module-level fixtures for SRE provider integration tests.
"""

from unittest.mock import MagicMock
import pytest


@pytest.fixture
def mock_respond():
    """Mock Slack respond function."""
    return MagicMock()


@pytest.fixture
def mock_ack():
    """Mock Slack ack function."""
    return MagicMock()


@pytest.fixture
def mock_client():
    """Mock Slack client."""
    return MagicMock()
