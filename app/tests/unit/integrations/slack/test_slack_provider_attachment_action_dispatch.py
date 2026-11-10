"""Unit tests for legacy-id aliases reaching their listener through real Bolt dispatch.

A real slack_bolt App (built with the library's own constructor, authorized for
one workspace, running listeners inline) replaces the provider's bootstrap, so
``initialize_app`` attaches the registered listeners exactly as at boot. Payloads
are form-encoded like Slack's own requests: a legacy ``interactive_message`` with a
legacy ``callback_id``, and a ``block_actions`` payload with a legacy ``action_id``.
Each must reach the new listener, which records the id it was invoked for.
"""

import json
from types import SimpleNamespace
from typing import Any, cast
from urllib.parse import urlencode

import pytest
from pydantic import SecretStr
from slack_bolt import App, BoltRequest

from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from integrations.slack.settings import SlackSettings
from tests.factories.slack_bolt import TEAM_ID, USER_ID, InlineExecutor, authorize_single_workspace, unpatched_app_init

pytestmark = pytest.mark.unit


@pytest.fixture
def bolt_app(monkeypatch: pytest.MonkeyPatch) -> App:
    monkeypatch.setattr(App, "__init__", unpatched_app_init())
    app = App(authorize=authorize_single_workspace, request_verification_enabled=False, listener_executor=InlineExecutor())
    monkeypatch.setattr("integrations.slack.provider.LegacySlackBootstrap", lambda: SimpleNamespace(create_app=lambda **_: app))
    monkeypatch.setattr("integrations.slack.provider.SocketModeHandler", lambda app, token, logger=None: SimpleNamespace(app=app))
    return app


@pytest.fixture
def provider(bolt_app: App) -> SlackPlatformProvider:
    settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
    return SlackPlatformProvider(settings=cast(SlackSettings, settings), formatter=SlackBlockKitFormatter())


def dispatch(app: App, payload: dict[str, Any]) -> int:
    body = urlencode({"payload": json.dumps({"team": {"id": TEAM_ID}, "user": {"id": USER_ID}, **payload})})
    return app.dispatch(BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})).status


def test_an_interactive_message_with_a_legacy_callback_id_reaches_the_new_listener(
    provider: SlackPlatformProvider, bolt_app: App
) -> None:
    received: list[str] = []

    def alert(ack: Any, body: dict[str, Any]) -> None:
        ack()
        received.append(body["callback_id"])

    provider.register_attachment_action("incident.response.alert", alert, legacy_callback_ids=("handle_incident_action_buttons",))
    assert provider.initialize_app().is_success

    status = dispatch(
        bolt_app,
        {
            "type": "interactive_message",
            "callback_id": "handle_incident_action_buttons",
            "actions": [{"name": "call-incident", "type": "button", "value": "alert-1"}],
            "channel": {"id": "C0ALERTS"},
        },
    )

    assert status == 200
    assert received == ["handle_incident_action_buttons"]


def test_a_block_action_with_a_legacy_action_id_reaches_the_new_listener(provider: SlackPlatformProvider, bolt_app: App) -> None:
    received: list[str] = []

    def acknowledge(ack: Any, body: dict[str, Any]) -> None:
        ack()
        received.append(body["actions"][0]["action_id"])

    provider.register_block_action("incident.response.acknowledge", acknowledge, legacy_action_ids=("ack_incident",))
    assert provider.initialize_app().is_success

    status = dispatch(
        bolt_app,
        {
            "type": "block_actions",
            "actions": [{"action_id": "ack_incident", "block_id": "b1", "type": "button", "value": "v"}],
            "channel": {"id": "C0ALERTS"},
        },
    )

    assert status == 200
    assert received == ["ack_incident"]
