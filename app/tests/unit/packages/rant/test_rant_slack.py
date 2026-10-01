"""Tests for the rant Slack platform handler."""

from unittest.mock import MagicMock

import pytest

from contracts.slack.models import CommandPayload, CommandResponse
from packages.rant.platforms import slack as rant_slack
from packages.rant.platforms.slack import handle_rant_command, register_commands
from packages.rant.service import UserIdentity, UserIdentityLookup


def _identities_with_profile(display_name="Ada Lovelace", icon_url="https://img/512.png"):
    """Build a fake identity lookup that resolves a usable name and avatar."""
    identities = MagicMock(spec=UserIdentityLookup)
    identities.lookup_user_identity.return_value = UserIdentity(display_name=display_name, icon_url=icon_url)
    return identities


@pytest.mark.unit
def test_handle_rant_command_posts_as_user_with_name_and_avatar():
    """A rant is posted with the invoking user's name and avatar."""
    client = MagicMock()
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client, _identities_with_profile())

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
    client = MagicMock()
    payload = CommandPayload(text="   ", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client, _identities_with_profile())

    assert result.ephemeral is True
    assert "/rant" in result.message
    client.chat_postMessage.assert_not_called()


@pytest.mark.unit
def test_handle_rant_command_falls_back_to_mention_when_post_as_user_fails():
    """A failed customized post falls back to a mention-prefixed bot message."""
    client = MagicMock()
    client.chat_postMessage.side_effect = Exception("missing_scope")
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client, _identities_with_profile())

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_identity_unavailable():
    """An unusable profile falls back to a mention-prefixed bot message."""
    client = MagicMock()
    identities = MagicMock(spec=UserIdentityLookup)
    identities.lookup_user_identity.return_value = None
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client, identities)

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"
    client.chat_postMessage.assert_not_called()


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_identity_lookup_raises():
    """A failed identity lookup falls back to a mention-prefixed bot message."""
    client = MagicMock()
    identities = MagicMock(spec=UserIdentityLookup)
    identities.lookup_user_identity.side_effect = RuntimeError("ratelimited")
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, client, identities)

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"
    client.chat_postMessage.assert_not_called()


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_no_client():
    """Without a client the command still posts via mention fallback."""
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, None, _identities_with_profile())

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
def test_registered_handler_uses_provider_client(monkeypatch):
    """The registered handler posts through the provider's Slack client, with the identity from the package lookup."""
    provider = MagicMock()
    monkeypatch.setattr(rant_slack, "get_user_identity_lookup", _identities_with_profile)
    register_commands(provider)
    handler = provider.register_command.call_args.kwargs["handler"]

    payload = CommandPayload(text="hi", user_id="U123", channel_id="C123")
    result = handler(payload)

    provider.client.chat_postMessage.assert_called_once()
    assert isinstance(result, CommandResponse)
