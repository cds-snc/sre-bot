"""Fixtures for platform provider tests.

Provides common mock settings and formatters for all provider tests,
following the hierarchical fixture architecture pattern.
"""

import pytest

from infrastructure.platforms.formatters.slack import SlackBlockKitFormatter
from infrastructure.platforms.formatters.teams import TeamsAdaptiveCardsFormatter


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


class MockTeamsSettings:
    """Mock Teams platform settings for testing."""

    def __init__(
        self,
        enabled=True,
        app_id="test-app-id",
        app_password="test-app-password",
        tenant_id="test-tenant-id",
    ):
        self.ENABLED = enabled
        self.APP_ID = app_id
        self.APP_PASSWORD = app_password
        self.TENANT_ID = tenant_id


class MockDiscordSettings:
    """Mock Discord platform settings for testing."""

    def __init__(
        self,
        enabled=False,
        bot_token=None,
        application_id=None,
        public_key=None,
    ):
        self.ENABLED = enabled
        self.BOT_TOKEN = bot_token
        self.APPLICATION_ID = application_id
        self.PUBLIC_KEY = public_key


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
# FIXTURE: TEAMS SETTINGS
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def teams_settings():
    """Provide mock Teams settings with defaults."""
    return MockTeamsSettings()


@pytest.fixture
def teams_settings_disabled():
    """Provide mock Teams settings with provider disabled."""
    return MockTeamsSettings(enabled=False)


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURE: DISCORD SETTINGS
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def discord_settings():
    """Provide mock Discord settings (out of scope, defaults to disabled)."""
    return MockDiscordSettings()


# ─────────────────────────────────────────────────────────────────────────────
# FIXTURE: FORMATTERS
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def slack_formatter():
    """Provide Slack BlockKit formatter."""
    return SlackBlockKitFormatter()


@pytest.fixture
def teams_formatter():
    """Provide Teams Adaptive Cards formatter."""
    return TeamsAdaptiveCardsFormatter()
