"""Fixtures for groups command unit tests."""

import pytest
from unittest.mock import MagicMock, patch
from tests.factories.groups_commands import make_groups_list_context


@pytest.fixture
def mock_translator():
    """Mock translator that returns input key."""

    def _translate(key: str, locale: str = "en-US", **variables):
        # Simple mock: replace {variable} with variable value
        result = key
        for var_name, var_value in variables.items():
            result = result.replace(f"{{{var_name}}}", str(var_value))
        return result

    return _translate


@pytest.fixture
def mock_command_context(mock_translator):
    """Create mock CommandContext for groups commands."""
    ctx = make_groups_list_context()
    ctx._translator = mock_translator  # pylint: disable=protected-access

    # Mock responder
    mock_responder = MagicMock()
    mock_responder.send_message = MagicMock()
    mock_responder.send_ephemeral = MagicMock()
    ctx._responder = mock_responder  # pylint: disable=protected-access

    return ctx


@pytest.fixture
def mock_groups_service():
    """Mock groups service module."""
    with patch("modules.groups.commands.handlers.service") as mock:
        yield mock


@pytest.fixture
def mock_slack_users():
    """Mock Slack users integration."""
    with patch("modules.groups.commands.handlers.slack_users") as mock:
        mock.get_user_email_from_handle.return_value = "resolved@example.com"
        yield mock


@pytest.fixture
def mock_groups_provider():
    """Mock groups provider."""
    with patch("modules.groups.commands.handlers.get_active_providers") as mock:
        mock.return_value = {
            "google": MagicMock(),
            "aws": MagicMock(),
            "azure": MagicMock(),
        }
        yield mock
