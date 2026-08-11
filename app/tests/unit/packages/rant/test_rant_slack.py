"""Tests for the rant Slack platform handler."""

from unittest.mock import MagicMock

import pytest

from integrations.slack.models import CommandPayload, CommandResponse
from packages.rant.platforms.slack import handle_rant_command, register_commands


@pytest.mark.unit
def test_handle_rant_command_posts_bold_uppercase_to_channel():
    """A non-empty rant is posted to the channel in bold uppercase."""
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload)

    assert isinstance(result, CommandResponse)
    assert result.ephemeral is False
    assert result.message == "*DEPLOYS KEEP FAILING*"


@pytest.mark.unit
def test_handle_rant_command_empty_text_returns_ephemeral_usage():
    """An empty rant returns an ephemeral usage hint and posts nothing."""
    payload = CommandPayload(text="   ", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload)

    assert result.ephemeral is True
    assert "/rant" in result.message


@pytest.mark.unit
def test_register_commands_registers_top_level_rant():
    """The command registers as a root command with no parent."""
    provider = MagicMock()

    register_commands(provider)

    provider.register_command.assert_called_once()
    kwargs = provider.register_command.call_args.kwargs
    assert kwargs["command"] == "rant"
    assert kwargs["handler"] is handle_rant_command
    assert kwargs.get("parent") is None
