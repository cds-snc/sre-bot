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
from typing import Any

import pytest
from slack_bolt import Ack
from slack_sdk import WebClient

from contracts.plugins.namespace import hookimpl
from contracts.slack.registrar import SlackCommandRegistrar
from tests.factories.slack_bolt import Harness, harness_fixture

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


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[Harness]:
    plugin = DemoPlugin()
    fixture_fn = harness_fixture(PLUGIN_NAME)
    yield from fixture_fn(monkeypatch, plugin)


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
