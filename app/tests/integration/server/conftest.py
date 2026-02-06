"""Fixtures for server integration tests."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_bot():
    """Create a mock Slack Bot for integration tests."""
    bot = MagicMock()
    bot.client = MagicMock()
    bot.say = MagicMock()
    return bot
