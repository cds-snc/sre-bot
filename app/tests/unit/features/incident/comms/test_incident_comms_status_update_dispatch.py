"""Dispatching ``/sre incident status-update`` through the real Slack provider.

The command takes no arguments, so the provider calls its handler with the
payload alone. These tests register the comms command on a real
``SlackPlatformProvider`` and route the command text the way Slack delivers it,
with the status-update handler stubbed and a fake scope opener resolving Slack
as configured, so a handler signature the provider
cannot call fails here rather than in a live workspace.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from contracts.slack.models import CommandPayload, CommandResponse
from features.incident.comms.entrypoints.slack import register
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from tests.factories.incident import incident_scopes
from tests.factories.services import FakeServiceScopeOpener


@pytest.fixture
def scopes() -> FakeServiceScopeOpener:
    return incident_scopes()


@pytest.fixture
def provider(scopes: FakeServiceScopeOpener) -> SlackPlatformProvider:
    settings: Any = SimpleNamespace(app_token="xapp-test", bot_token="xoxb-test")
    slack_provider = SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter())
    slack_provider.set_scope_opener(scopes)
    register(slack_provider)
    return slack_provider


@pytest.mark.parametrize("text", ["incident status-update", "incident status-update  "])
def test_status_update_routes_from_sre_to_its_handler_with_the_payload(
    provider: SlackPlatformProvider, scopes: FakeServiceScopeOpener, text: str
) -> None:
    """``/sre incident status-update`` reaches the handler with the payload, empty args, the reply sender and the scope opener."""
    payload = CommandPayload(
        text=text, user_id="U9", channel_id="C1", user_locale="fr-FR", platform_metadata={"trigger_id": "T1"}
    )
    handler = MagicMock(return_value=CommandResponse(message="", ephemeral=True))

    with patch("features.incident.comms.entrypoints.slack.handle_status_update_command", handler):
        response = provider.route_hierarchical_command("sre", text, payload)

    handler.assert_called_once()
    called_payload, called_args, called_reply, called_scopes = handler.call_args.args
    assert called_payload is payload
    assert called_args == {}
    assert called_reply is provider.reply
    assert called_scopes is scopes
    assert response is handler.return_value
