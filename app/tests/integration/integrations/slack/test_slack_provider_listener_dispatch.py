"""Integration tests that dispatch block actions and view submissions through a real Bolt app.

A plugin registered on a real pluggy PluginManager under a dotted entry-point
name registers its listeners through ``register_feature_integrations`` onto a
real ``SlackPlatformProvider``, which attaches them to a real ``slack_bolt.App``.
Interaction payloads are form-encoded as Slack posts them and fed to
``App.dispatch``; listeners run inline. Only the Web API edge is stubbed:
``WebClient.api_call`` records the calls a listener makes through Bolt's own
``client``, so the tests can prove a modal is opened without a network.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import urlencode

import pluggy
import pytest
from slack_bolt import Ack, App, BoltRequest, BoltResponse
from slack_sdk import WebClient

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE, hookimpl
from contracts.slack.registrar import SlackCommandRegistrar
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from server.plugins.manager import register_feature_integrations
from tests.factories.slack_bolt import TEAM_ID, InlineExecutor, authorize_single_workspace, unpatched_app_init

pytestmark = pytest.mark.integration

PLUGIN_NAME = "demo.feature"
OPEN_ACTION_ID = f"{PLUGIN_NAME}.open"
SUBMIT_CALLBACK_ID = f"{PLUGIN_NAME}.submit"
USER_ID = "U0APPROVER"
TRIGGER_ID = "trigger-456"


@dataclass
class DemoPlugin:
    """Opens a modal from a button and validates the modal's single text field."""

    clicked: list[dict[str, Any]] = field(default_factory=list)
    submitted: list[str] = field(default_factory=list)

    @hookimpl
    def register_slack_commands(self, registrar: SlackCommandRegistrar) -> None:
        registrar.register_block_action(OPEN_ACTION_ID, self.open_modal)
        registrar.register_view_submission(SUBMIT_CALLBACK_ID, self.submit)

    def open_modal(self, ack: Ack, body: dict[str, Any], client: WebClient) -> None:
        ack()
        self.clicked.append(body)
        client.views_open(trigger_id=body["trigger_id"], view={"type": "modal", "callback_id": SUBMIT_CALLBACK_ID})

    def submit(self, ack: Ack, view: dict[str, Any]) -> None:
        summary = view["state"]["values"]["summary"]["text"]["value"] or ""
        if not summary.strip():
            ack(response_action="errors", errors={"summary": "Enter a summary"})
            return
        ack()
        self.submitted.append(summary)


@dataclass
class Harness:
    app: App
    plugin: DemoPlugin
    api_calls: list[tuple[str, dict[str, Any]]]

    def dispatch(self, payload: dict[str, Any]) -> BoltResponse:
        body = urlencode({"payload": json.dumps({"team": {"id": TEAM_ID}, "user": {"id": USER_ID}, **payload})})
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    monkeypatch.setattr(App, "__init__", unpatched_app_init())
    api_calls: list[tuple[str, dict[str, Any]]] = []

    def record_api_call(self: WebClient, api_method: str, **kwargs: Any) -> dict[str, Any]:
        api_calls.append((api_method, kwargs.get("json") or kwargs.get("params") or {}))
        return {"ok": True}

    monkeypatch.setattr(WebClient, "api_call", record_api_call)

    plugin = DemoPlugin()
    plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    plugin_manager.add_hookspecs(FeatureLifecycleSpecs)
    plugin_manager.register(plugin, name=PLUGIN_NAME)
    monkeypatch.setattr("server.plugins.manager.get_plugin_manager", lambda: plugin_manager)

    app = App(authorize=authorize_single_workspace, request_verification_enabled=False, listener_executor=InlineExecutor())
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    provider = SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter())
    monkeypatch.setattr("integrations.slack.provider.LegacySlackBootstrap", lambda: SimpleNamespace(create_app=lambda: app))
    monkeypatch.setattr("integrations.slack.provider.SocketModeHandler", lambda app, token: SimpleNamespace(app=app))

    register_feature_integrations(app=MagicMock(), logger=MagicMock(), slack_provider=provider)
    assert provider.initialize_app().is_success

    yield Harness(app=app, plugin=plugin, api_calls=api_calls)


def block_action(action_id: str) -> dict[str, Any]:
    return {
        "type": "block_actions",
        "trigger_id": TRIGGER_ID,
        "channel": {"id": "C0INCIDENT"},
        "actions": [{"action_id": action_id, "block_id": "approval", "type": "button", "value": "draft-1"}],
    }


def view_submission(summary: str | None) -> dict[str, Any]:
    return {
        "type": "view_submission",
        "trigger_id": TRIGGER_ID,
        "view": {
            "id": "V0MODAL",
            "type": "modal",
            "callback_id": SUBMIT_CALLBACK_ID,
            "private_metadata": "",
            "state": {"values": {"summary": {"text": {"type": "plain_text_input", "value": summary}}}},
        },
    }


def test_block_action_is_acked_and_its_listener_opens_a_modal_with_bolts_client(harness: Harness) -> None:
    response = harness.dispatch(block_action(OPEN_ACTION_ID))

    assert response.status == 200
    assert response.body == ""
    (body,) = harness.plugin.clicked
    assert body["actions"][0]["value"] == "draft-1"
    assert harness.api_calls == [
        ("views.open", {"trigger_id": TRIGGER_ID, "view": {"type": "modal", "callback_id": SUBMIT_CALLBACK_ID}})
    ]


def test_valid_view_submission_is_acked_empty_and_handled(harness: Harness) -> None:
    response = harness.dispatch(view_submission("Service restored"))

    assert response.status == 200
    assert response.body == ""
    assert harness.plugin.submitted == ["Service restored"]


@pytest.mark.parametrize("summary", ["", "   ", None])
def test_invalid_view_submission_acks_with_field_errors(harness: Harness, summary: str | None) -> None:
    response = harness.dispatch(view_submission(summary))

    assert response.status == 200
    assert json.loads(response.body) == {"response_action": "errors", "errors": {"summary": "Enter a summary"}}
    assert harness.plugin.submitted == []


def test_unregistered_action_id_never_reaches_the_listener(harness: Harness) -> None:
    response = harness.dispatch(block_action(f"{PLUGIN_NAME}.other"))

    assert response.status == 404
    assert harness.plugin.clicked == []
    assert harness.api_calls == []
