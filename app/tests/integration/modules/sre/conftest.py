"""Integration test fixtures for SRE module.

Module-level fixtures for SRE platform integration tests.
Follows new platform architecture patterns.
"""

from unittest.mock import MagicMock

import pytest

from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter
from infrastructure.platforms.providers.slack import SlackPlatformProvider
from modules.sre.platforms import slack as sre_slack


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


@pytest.fixture
def slack_settings():
    """Mock Slack platform settings for testing."""

    class MockSlackSettings:
        ENABLED = True
        SOCKET_MODE = True
        APP_TOKEN = "xapp-test"
        BOT_TOKEN = "xoxb-test"
        SIGNING_SECRET = "test-secret"

    return MockSlackSettings()


@pytest.fixture
def slack_formatter():
    """Slack formatter instance for testing."""
    return SlackBlockKitFormatter()


@pytest.fixture
def slack_provider(slack_settings, slack_formatter, monkeypatch):
    """SlackPlatformProvider instance for testing command registration.

    Mocks the Slack Bolt App initialization to avoid network calls.
    """

    # Mock Slack Bolt classes
    class FakeApp:
        def __init__(self, token=None):
            self.client = MagicMock()

    class FakeSocketModeHandler:
        def __init__(self, app, token):
            self.app = app
            self.token = token

        def connect(self):
            return None

    monkeypatch.setattr("infrastructure.platforms.providers.slack.App", FakeApp)
    monkeypatch.setattr(
        "infrastructure.platforms.providers.slack.SocketModeHandler",
        FakeSocketModeHandler,
    )

    provider = SlackPlatformProvider(
        settings=slack_settings,
        formatter=slack_formatter,
    )
    return provider


@pytest.fixture
def mock_slack_client(monkeypatch):
    """Mock SlackClientFacade for integration tests."""
    mock_facade = MagicMock()
    mock_facade.raw_client = MagicMock()

    monkeypatch.setattr(sre_slack, "get_slack_client", lambda: mock_facade)

    return mock_facade
