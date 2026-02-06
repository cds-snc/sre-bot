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
def mock_settings():
    """Create a mock settings object."""
    settings = MagicMock()
    settings.is_production = False
    settings.server = MagicMock()
    settings.server.SECRET_KEY = "test_secret_key"
    settings.server.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    settings.server.ACCESS_TOKEN_MAX_AGE_MINUTES = 60
    settings.slack = MagicMock()
    settings.slack.SLACK_TOKEN = "xoxb-test-token"
    settings.slack.APP_TOKEN = "xapp-test-token"
    settings.PREFIX = ""
    return settings


@pytest.fixture
def mock_bot():
    """Create a mock Slack Bot."""
    bot = MagicMock()
    bot.client = MagicMock()
    bot.say = MagicMock()
    return bot
