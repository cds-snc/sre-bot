"""Fixtures for SRE module unit tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_respond():
    """Mock responder for SRE commands."""
    return MagicMock()


@pytest.fixture
def mock_client():
    """Mock Slack client for SRE commands."""
    return MagicMock()


@pytest.fixture
def mock_body():
    """Mock Slack body/payload."""
    return {"channel_id": "C123456"}
