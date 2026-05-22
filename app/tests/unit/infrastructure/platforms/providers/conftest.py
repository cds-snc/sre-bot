"""Fixtures for platform provider tests.

Provides common mock settings and formatters for all provider tests,
following the hierarchical fixture architecture pattern.
"""

import pytest

from integrations.slack.formatter import SlackBlockKitFormatter

# ─────────────────────────────────────────────────────────────────────────────
# MOCK SETTINGS FACTORIES
# ─────────────────────────────────────────────────────────────────────────────


class MockSlackSettings:
    """Mock Slack platform settings for testing."""

    def __init__(
        self,
        enabled=True,
        socket_mode=True,
        app_token="xapp-test",
        bot_token="xoxb-test",
        signing_secret="test-secret",
    ):
        self.ENABLED = enabled
        self.SOCKET_MODE = socket_mode
        self.APP_TOKEN = app_token
        self.BOT_TOKEN = bot_token
        self.SIGNING_SECRET = signing_secret


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURE: SLACK SETTINGS
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def slack_settings():
    """Provide mock Slack settings with defaults."""
    return MockSlackSettings()


@pytest.fixture
def slack_settings_disabled():
    """Provide mock Slack settings with provider disabled."""
    return MockSlackSettings(enabled=False)


@pytest.fixture
def slack_settings_http_mode():
    """Provide mock Slack settings in HTTP webhook mode."""
    return MockSlackSettings(socket_mode=False, signing_secret="webhook-secret")


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURE: FORMATTERS
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def slack_formatter():
    """Provide Slack BlockKit formatter."""
    return SlackBlockKitFormatter()
