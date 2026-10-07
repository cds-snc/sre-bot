"""Dispatching ``/sre incident status-update`` through the real Slack provider.

The command takes no arguments, so the provider calls its handler with the
payload alone. These tests register the scribe commands on a real
``SlackPlatformProvider`` and route the command text the way Slack delivers it,
with the status-update handler stubbed, so a handler signature the provider
cannot call fails here rather than in a live workspace.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from contracts.slack.models import CommandPayload, CommandResponse
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from packages.incident.scribe.platforms.slack import register_commands


@pytest.fixture
def provider() -> SlackPlatformProvider:
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    slack_provider = SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter())
    register_commands(slack_provider)
    return slack_provider


@pytest.mark.parametrize("text", ["incident status-update", "incident status-update  "])
def test_status_update_routes_from_sre_to_its_handler_with_the_payload(
    provider: SlackPlatformProvider, text: str
) -> None:
    """``/sre incident status-update`` reaches the handler with the payload, empty args and the provider's reply sender."""
    payload = CommandPayload(
        text=text, user_id="U9", channel_id="C1", user_locale="fr-FR", platform_metadata={"trigger_id": "T1"}
    )
    handler = MagicMock(return_value=CommandResponse(message="", ephemeral=True))

    with patch("packages.incident.scribe.platforms.slack.handle_status_update_command", handler):
        response = provider.route_hierarchical_command("sre", text, payload)

    handler.assert_called_once()
    called_payload, called_args, called_reply = handler.call_args.args
    assert called_payload is payload
    assert called_args == {}
    assert called_reply is provider.reply
    assert response is handler.return_value
