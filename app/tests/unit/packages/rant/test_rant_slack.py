"""Tests for the rant Slack platform handler."""

from unittest.mock import MagicMock

import pytest

from contracts.operations import OperationResult, OperationStatus
from contracts.slack.models import CommandPayload, CommandResponse
from packages.rant.platforms import slack as rant_slack
from packages.rant.platforms.slack import handle_rant_command, register_commands
from packages.rant.service import UserIdentity, UserIdentityLookup
from tests.factories.slack import FakeSlackRegistrar, FakeSlackReply


def _identities_with_profile(display_name="Ada Lovelace", icon_url="https://img/512.png"):
    """Build a fake identity lookup that resolves a usable name and avatar."""
    identities = MagicMock(spec=UserIdentityLookup)
    identities.lookup_user_identity.return_value = UserIdentity(display_name=display_name, icon_url=icon_url)
    return identities


@pytest.mark.unit
def test_handle_rant_command_posts_as_user_with_name_and_avatar():
    """A rant is posted with the invoking user's name and avatar."""
    reply = FakeSlackReply()
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, reply, _identities_with_profile())

    assert reply.calls == [
        (
            "post_message",
            {
                "channel_id": "C123",
                "text": "*DEPLOYS KEEP FAILING*",
                "username": "Ada Lovelace",
                "icon_url": "https://img/512.png",
            },
        )
    ]
    assert result.ephemeral is True


@pytest.mark.unit
def test_handle_rant_command_empty_text_returns_ephemeral_usage():
    """An empty rant returns an ephemeral usage hint and posts nothing."""
    reply = FakeSlackReply()
    payload = CommandPayload(text="   ", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, reply, _identities_with_profile())

    assert result.ephemeral is True
    assert "/rant" in result.message
    assert reply.calls == []


@pytest.mark.unit
def test_handle_rant_command_falls_back_to_mention_when_post_as_user_fails():
    """A failed customized post falls back to a mention-prefixed bot message."""
    reply = FakeSlackReply(OperationResult.error(OperationStatus.UNAUTHORIZED, "missing scope", error_code="missing_scope"))
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, reply, _identities_with_profile())

    assert len(reply.calls_to("post_message")) == 1
    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_identity_unavailable():
    """An unusable profile falls back to a mention-prefixed bot message."""
    reply = FakeSlackReply()
    identities = MagicMock(spec=UserIdentityLookup)
    identities.lookup_user_identity.return_value = None
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, reply, identities)

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"
    assert reply.calls == []


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_identity_lookup_raises():
    """A failed identity lookup falls back to a mention-prefixed bot message."""
    reply = FakeSlackReply()
    identities = MagicMock(spec=UserIdentityLookup)
    identities.lookup_user_identity.side_effect = RuntimeError("ratelimited")
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id="C123")

    result = handle_rant_command(payload, reply, identities)

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"
    assert reply.calls == []


@pytest.mark.unit
def test_handle_rant_command_falls_back_when_no_channel():
    """Without a channel to post in, the command answers via mention fallback and posts nothing."""
    reply = FakeSlackReply()
    payload = CommandPayload(text="deploys keep failing", user_id="U123", channel_id=None)

    result = handle_rant_command(payload, reply, _identities_with_profile())

    assert result.ephemeral is False
    assert result.message == "<@U123> ranted: *DEPLOYS KEEP FAILING*"
    assert reply.calls == []


@pytest.mark.unit
def test_register_commands_registers_top_level_rant():
    """The command registers as a root command with no parent."""
    registrar = FakeSlackRegistrar()

    register_commands(registrar)

    (entry,) = registrar.commands
    assert entry["command"] == "rant"
    assert callable(entry["handler"])
    assert entry["parent"] is None


@pytest.mark.unit
def test_registered_handler_replies_through_the_registrar(monkeypatch):
    """The registered handler posts through the registrar's reply interface, with the identity from the package lookup."""
    reply = FakeSlackReply()
    registrar = FakeSlackRegistrar(reply)
    monkeypatch.setattr(rant_slack, "get_user_identity_lookup", _identities_with_profile)
    register_commands(registrar)
    handler = registrar.command("rant")["handler"]

    payload = CommandPayload(text="hi", user_id="U123", channel_id="C123")
    result = handler(payload)

    assert len(reply.calls_to("post_message")) == 1
    assert isinstance(result, CommandResponse)
