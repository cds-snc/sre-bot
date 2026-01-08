"""Shared fixtures for command infrastructure integration tests."""

import pytest


@pytest.fixture
def mock_settings(make_mock_settings):
    """Create mock settings for command provider integration tests.

    This fixture is shared across all command integration tests
    and provides a MagicMock settings object with Slack-specific
    pre-configuration.

    Uses the factory from root conftest to avoid duplication
    across different test packages.
    """
    return make_mock_settings(
        **{
            "slack.SLACK_TOKEN": "xoxb-test-token",
            "commands.providers": {},
        }
    )
