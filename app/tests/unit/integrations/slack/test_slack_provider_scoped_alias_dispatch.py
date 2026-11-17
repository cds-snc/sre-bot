"""Unit tests for value-scoped legacy attachment aliases through real Bolt dispatch.

A real slack_bolt App (built with the library's own constructor, authorized for
one workspace, running listeners inline) replaces the provider's bootstrap, so
``initialize_app`` attaches the registered listeners exactly as at boot. A legacy
listener is then attached with ``app.action`` after ``initialize_app``, in the
order the host uses for the legacy modules. Payloads are form-encoded legacy
``interactive_message`` clicks on one posted callback id with different button
values. Each listener records the value it was invoked for, so the assertions
show which listener Bolt ran: a claimed value reaches its rebuilt listener only,
anything else falls through to the legacy listener.
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

CALLBACK = "archive_channel"


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


def recorder(name: str, calls: list[tuple[str, str | None]]) -> Any:
    def listener(ack: Any, body: dict[str, Any]) -> None:
        ack()
        actions = body.get("actions") or [{}]
        calls.append((name, actions[0].get("value")))

    return listener


def click(app: App, actions: list[dict[str, Any]]) -> int:
    payload = {
        "team": {"id": TEAM_ID},
        "user": {"id": USER_ID},
        "type": "interactive_message",
        "callback_id": CALLBACK,
        "actions": actions,
        "channel": {"id": "C0INCIDENT"},
    }
    body = urlencode({"payload": json.dumps(payload)})
    return app.dispatch(BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})).status


def button(value: str) -> list[dict[str, Any]]:
    return [{"name": value, "type": "button", "value": value}]


def test_a_claimed_value_reaches_the_rebuilt_listener_only(provider: SlackPlatformProvider, bolt_app: App) -> None:
    calls: list[tuple[str, str | None]] = []
    provider.register_attachment_action(
        "incident.response.archive", recorder("archive", calls), legacy_callback_values={CALLBACK: ("archive",)}
    )
    assert provider.initialize_app().is_success
    bolt_app.action(CALLBACK)(recorder("legacy", calls))

    assert click(bolt_app, button("archive")) == 200

    assert calls == [("archive", "archive")]


def test_an_unclaimed_value_reaches_a_legacy_listener_attached_later(provider: SlackPlatformProvider, bolt_app: App) -> None:
    calls: list[tuple[str, str | None]] = []
    provider.register_attachment_action(
        "incident.response.archive", recorder("archive", calls), legacy_callback_values={CALLBACK: ("archive",)}
    )
    assert provider.initialize_app().is_success
    bolt_app.action(CALLBACK)(recorder("legacy", calls))

    assert click(bolt_app, button("schedule_retro")) == 200

    assert calls == [("legacy", "schedule_retro")]


def test_listeners_sharing_a_callback_each_get_their_own_values(provider: SlackPlatformProvider, bolt_app: App) -> None:
    calls: list[tuple[str, str | None]] = []
    provider.register_attachment_action(
        "incident.response.archive", recorder("archive", calls), legacy_callback_values={CALLBACK: ("archive",)}
    )
    provider.register_attachment_action(
        "incident.postmortem.schedule", recorder("schedule", calls), legacy_callback_values={CALLBACK: ("schedule_retro",)}
    )
    assert provider.initialize_app().is_success
    bolt_app.action(CALLBACK)(recorder("legacy", calls))

    for value in ("archive", "schedule_retro", "ignore"):
        assert click(bolt_app, button(value)) == 200

    assert calls == [("archive", "archive"), ("schedule", "schedule_retro"), ("legacy", "ignore")]


def test_a_click_without_a_value_reaches_the_legacy_listener(provider: SlackPlatformProvider, bolt_app: App) -> None:
    calls: list[tuple[str, str | None]] = []
    provider.register_attachment_action(
        "incident.response.archive", recorder("archive", calls), legacy_callback_values={CALLBACK: ("archive",)}
    )
    assert provider.initialize_app().is_success
    bolt_app.action(CALLBACK)(recorder("legacy", calls))

    assert click(bolt_app, [{"name": "archive", "type": "button"}]) == 200

    assert calls == [("legacy", None)]
