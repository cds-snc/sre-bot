"""Fixtures for command provider tests."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True, scope="function")
def mock_slack_settings(monkeypatch):
    """Mock Slack settings for all tests in this directory.

    This ensures SlackCommandProvider can be instantiated in tests
    without requiring actual Slack configuration.
    """
    mock_settings = MagicMock()
    mock_settings.slack.SLACK_TOKEN = "xoxb-test-token"

    # Patch both where settings is used and where it's defined
    monkeypatch.setattr("core.config.settings", mock_settings)
    monkeypatch.setattr(
        "infrastructure.commands.providers.slack.settings", mock_settings
    )

    return mock_settings
