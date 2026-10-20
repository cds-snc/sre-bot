"""Fixtures for server module unit tests."""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI


@pytest.fixture
def mock_fastapi_app():
    """Create a mock FastAPI application."""
    app = MagicMock(spec=FastAPI)
    app.routes = []
    app.user_middleware = []
    app.dependency_overrides = {}
    return app


@pytest.fixture
def mock_bot():
    """Create a mock Slack Bot."""
    bot = MagicMock()
    bot.client = MagicMock()
    bot.say = MagicMock()
    return bot
