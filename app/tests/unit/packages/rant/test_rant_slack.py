"""Tests for the rant Slack platform handler."""

from unittest.mock import MagicMock

import pytest

from integrations.slack.models import CommandPayload, CommandResponse
from packages.rant.platforms.slack import handle_rant_command, register_commands


def _client_with_profile(display_name="Ada Lovelace", icon_url="https://img/512.png"):
    """Build a mock Slack client whose users_info returns a usable profile."""
    client = MagicMock()
    client.users_info.return_value = {
        "ok": True,
        "user": {
            "profile": {
                "display_name": display_name,
                "real_name": display_name,
                "image_512": icon_url,
            }
        },
    }
    return client


@pytest.mark.unit
def test_handle_rant_command_posts_as_user_with_name_and_avatar():
    """A rant is posted with the invoking user's name and avatar."""
    client = _client_with_profile()
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client)

    client.chat_postMessage.assert_called_once_with(
        channel="C123",
        text="*DEPLOYS KEEP FAILING*",
        username="Ada Lovelace",
        icon_url="https://img/512.png",
    )
    assert result.ephemeral is True


@pytest.mark.unit
def test_handle_rant_command_empty_text_returns_ephemeral_usage():
    """An empty rant returns an ephemeral usage hint and posts nothing."""
    client = _client_with_profile()
    payload = CommandPayload(text="   ", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client)

    assert result.ephemeral is True
    assert "/rant" in result.message
    client.chat_postMessage.assert_not_called()


@pytest.mark.unit
def test_handle_rant_command_falls_back_to_mention_when_post_as_user_fails():
    """A failed customized post falls back to a mention-prefixed bot message."""
    client = _client_with_profile()
    client.chat_postMessage.side_effect = Exception("missing_scope")
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client)

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_identity_unavailable():
    """An unusable profile falls back to a mention-prefixed bot message."""
    client = MagicMock()
    client.users_info.return_value = {"ok": False, "error": "user_not_found"}
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client)

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"
    client.chat_postMessage.assert_not_called()


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_no_client():
    """Without a client the command still posts via mention fallback."""
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, None)

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"


@pytest.mark.unit
def test_register_commands_registers_top_level_rant():
    """The command registers as a root command with no parent."""
    provider = MagicMock()

    register_commands(provider)

    provider.register_command.assert_called_once()
    kwargs = provider.register_command.call_args.kwargs
    assert kwargs["command"] == "rant"
    assert callable(kwargs["handler"])
    assert kwargs.get("parent") is None


@pytest.mark.unit
def test_registered_handler_uses_provider_client():
    """The registered handler dispatches through the provider's Slack client."""
    provider = MagicMock()
    provider.client = _client_with_profile()
    register_commands(provider)
    handler = provider.register_command.call_args.kwargs["handler"]

    payload = CommandPayload(text="hi", user_id="U123", channel_id="C123")
    result = handler(payload)

    provider.client.chat_postMessage.assert_called_once()
    assert isinstance(result, CommandResponse)
