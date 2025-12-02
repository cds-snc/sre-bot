"""Feature-level fixtures for command framework tests (Level 3)."""

from unittest.mock import MagicMock
import pytest

from infrastructure.commands.parser import CommandParser
from infrastructure.commands.context import CommandContext


@pytest.fixture
def command_context_factory():
    """Factory for creating CommandContext instances for testing.

    Returns:
        Callable that creates CommandContext with default or custom values
    """

    def _factory(
        platform: str = "slack",
        user_id: str = "U12345",
        user_email: str = "test@example.com",
        channel_id: str = "C12345",
        locale: str = "en-US",
        metadata: dict = None,
        correlation_id: str = None,
        translator=None,
        responder=None,
    ):
        ctx = CommandContext(
            platform=platform,
            user_id=user_id,
            user_email=user_email,
            channel_id=channel_id,
            locale=locale,
            metadata=metadata or {},
            correlation_id=correlation_id,
        )
        if translator is not None:
            ctx._translator = translator
        if responder is not None:
            ctx._responder = responder
        return ctx

    return _factory


@pytest.fixture
def mock_translator():
    """Mock translation function for CommandContext.

    Returns:
        Callable that formats translated keys with variables for testing
    """

    def _translate(key: str, locale: str, **variables):
        """Simple mock translator that prefixes with locale."""
        vars_str = (
            ",".join(f"{k}={v}" for k, v in variables.items()) if variables else ""
        )
        return f"translated[{locale}]:{key}" + (f"[{vars_str}]" if vars_str else "")

    return _translate


@pytest.fixture
def mock_response_channel():
    """Mock ResponseChannel for CommandContext.

    Returns:
        MagicMock with send_message and send_ephemeral methods
    """
    channel = MagicMock()
    channel.send_message = MagicMock()
    channel.send_ephemeral = MagicMock()
    return channel


@pytest.fixture
def command_parser():
    """CommandParser instance for parsing tests."""
    return CommandParser()


@pytest.fixture
def mock_slack_client():
    """Mock Slack client for adapter tests.

    Returns:
        MagicMock configured with common Slack API methods
    """
    client = MagicMock()
    client.users_info = MagicMock(
        return_value={
            "ok": True,
            "user": {"profile": {"email": "test@example.com"}},
        }
    )
    client.chat_postEphemeral = MagicMock(return_value={"ok": True})
    return client


@pytest.fixture
def mock_slack_respond():
    """Mock Slack respond function for adapter tests.

    Returns:
        MagicMock that captures response calls
    """
    return MagicMock()


@pytest.fixture
def mock_slack_ack():
    """Mock Slack acknowledgment function for adapter tests.

    Returns:
        MagicMock for command acknowledgment
    """
    return MagicMock()


@pytest.fixture
def slack_command_payload():
    """Sample Slack slash command payload.

    Returns:
        dict with typical Slack command structure
    """
    return {
        "command": "/sre",
        "text": "groups list",
        "user_id": "U123456",
        "user_name": "testuser",
        "channel_id": "C123456",
        "channel_name": "general",
        "team_id": "T123456",
        "team_domain": "example",
        "response_url": "https://hooks.slack.com/commands/T123456/...",
        "trigger_id": "trigger-123",
    }
