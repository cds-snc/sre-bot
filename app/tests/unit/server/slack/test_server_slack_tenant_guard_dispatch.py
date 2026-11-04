"""Unit tests for the Slack tenant guard on a real Bolt app.

A real slack_bolt App (unpatched_app_init, static single-workspace
authorization, listeners run inline) has the guard installed and one listener
per request type that records its call. Requests are built as Slack sends them:
form-encoded commands and interaction payloads, JSON Events API callbacks.
WebhookClient is replaced by a recorder, so the ephemeral notice is observed
without network access, and the notice executor runs inline. Log events are
captured with structlog's capture_logs. Assertions cover what Slack and the
user see (the ack status and body, the notice) and what an operator sees (one
slack_tenant_mismatch event naming the ids and never the payload text).
"""

import json
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlencode

import pytest
from slack_bolt import App, BoltRequest, BoltResponse
from structlog.testing import capture_logs

from integrations.slack.settings import SlackTenant
from server.slack import tenant_guard
from server.slack.tenant_guard import install_slack_tenant_guard
from tests.factories.slack_bolt import TEAM_ID, InlineExecutor, authorize_single_workspace, unpatched_app_init

pytestmark = pytest.mark.unit

OTHER_TEAM = "T0OTHER"
RESPONSE_URL = "https://hooks.slack.com/commands/T0/1/secret-path"
SECRET_TEXT = "secret user text"


class RecordingWebhook:
    """Stands in for slack_sdk's WebhookClient and records each ephemeral notice."""

    sent: list[dict[str, Any]] = []
    fail = False

    def __init__(self, url: str, timeout: int) -> None:
        self.url = url
        self.timeout = timeout

    def send(self, **kwargs: Any) -> Any:
        if RecordingWebhook.fail:
            raise TimeoutError("response_url did not answer")
        RecordingWebhook.sent.append({"url": self.url, "timeout": self.timeout, **kwargs})
        return None


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    RecordingWebhook.sent = []
    RecordingWebhook.fail = False
    monkeypatch.setattr(tenant_guard, "WebhookClient", RecordingWebhook)
    yield []


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> App:
    monkeypatch.setattr(App, "__init__", unpatched_app_init())
    bolt = App(authorize=authorize_single_workspace, request_verification_enabled=False, listener_executor=InlineExecutor())
    install_slack_tenant_guard(bolt, SlackTenant(team_id=TEAM_ID), executor=InlineExecutor())

    def record(name: str) -> Any:
        def listener(ack: Any) -> None:
            calls.append(name)
            ack()

        return listener

    bolt.command("/sre")(record("command"))
    bolt.action("approve")(record("block_actions"))
    bolt.view("modal")(record("view_submission"))
    bolt.view_closed("modal")(record("view_closed"))
    bolt.shortcut("message_shortcut")(record("message_action"))
    bolt.options("pick")(record("block_suggestion"))
    bolt.event("app_mention")(record("event"))
    return bolt


def _form(body: dict[str, Any]) -> BoltRequest:
    return BoltRequest(body=urlencode(body), headers={"content-type": ["application/x-www-form-urlencoded"]})


def _interaction(payload: dict[str, Any]) -> BoltRequest:
    return _form({"payload": json.dumps(payload)})


def _command(team_id: str) -> BoltRequest:
    return _form(
        {
            "command": "/sre",
            "text": SECRET_TEXT,
            "team_id": team_id,
            "user_id": "U0USER",
            "channel_id": "C0CHAN",
            "response_url": RESPONSE_URL,
            "trigger_id": "trigger-1",
        }
    )


def _event(team_id: str, user_team: str | None = None) -> BoltRequest:
    event: dict[str, Any] = {"type": "app_mention", "user": "U0USER", "text": SECRET_TEXT, "channel": "C0CHAN"}
    if user_team is not None:
        event["user_team"] = user_team
        event["source_team"] = user_team
    body = {
        "type": "event_callback",
        "team_id": team_id,
        "api_app_id": "A0APP",
        "event": event,
        "authorizations": [{"team_id": team_id, "enterprise_id": None, "is_enterprise_install": False, "user_id": "UBOT"}],
    }
    return BoltRequest(body=json.dumps(body), headers={"content-type": ["application/json"]})


def _requests(team_id: str) -> dict[str, BoltRequest]:
    team = {"id": team_id}
    user = {"id": "U0USER", "team_id": team_id}
    view = {"id": "V0", "type": "modal", "callback_id": "modal", "team_id": team_id, "state": {"values": {}}}
    return {
        "command": _command(team_id),
        "block_actions": _interaction(
            {
                "type": "block_actions",
                "team": team,
                "user": user,
                "response_url": RESPONSE_URL,
                "trigger_id": "trigger-1",
                "actions": [{"action_id": "approve", "block_id": "b", "type": "button", "value": SECRET_TEXT}],
            }
        ),
        "view_submission": _interaction({"type": "view_submission", "team": team, "user": user, "view": view}),
        "view_closed": _interaction({"type": "view_closed", "team": team, "user": user, "view": view}),
        "message_action": _interaction(
            {
                "type": "message_action",
                "callback_id": "message_shortcut",
                "team": team,
                "user": user,
                "channel": {"id": "C0CHAN"},
                "message": {"text": SECRET_TEXT},
                "response_url": RESPONSE_URL,
                "trigger_id": "trigger-1",
            }
        ),
        "block_suggestion": _interaction(
            {"type": "block_suggestion", "action_id": "pick", "block_id": "b", "team": team, "user": user, "value": "x"}
        ),
        "event": _event(team_id),
    }


REQUEST_TYPES = list(_requests(TEAM_ID))
WITH_RESPONSE_URL = {"command", "block_actions", "message_action"}


def _mismatches(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry["event"] == "slack_tenant_mismatch"]


@pytest.mark.parametrize("request_type", REQUEST_TYPES)
def test_matching_request_reaches_its_listener(app: App, calls: list[str], request_type: str) -> None:
    """A request from the configured workspace passes the guard unchanged and runs its listener."""
    with capture_logs() as entries:
        response = app.dispatch(_requests(TEAM_ID)[request_type])

    assert response.status == 200
    assert calls == [request_type]
    assert not _mismatches(entries)
    assert RecordingWebhook.sent == []


@pytest.mark.parametrize("request_type", REQUEST_TYPES)
def test_request_from_another_workspace_is_acked_and_runs_no_listener(app: App, calls: list[str], request_type: str) -> None:
    """A refused request is acked, so Slack shows no timeout, and no listener runs."""
    with capture_logs():
        response = app.dispatch(_requests(OTHER_TEAM)[request_type])

    assert response.status == 200
    assert calls == []


def test_refused_options_request_is_acked_with_no_options(app: App) -> None:
    """A select menu's options request needs an options body even when refused."""
    with capture_logs():
        response: BoltResponse = app.dispatch(_requests(OTHER_TEAM)["block_suggestion"])

    assert json.loads(response.body) == {"options": []}


@pytest.mark.parametrize("request_type", REQUEST_TYPES)
def test_refused_request_logs_one_mismatch_with_the_ids_and_no_payload_text(app: App, request_type: str) -> None:
    """The operator sees which tenant was expected and which arrived, never what the user wrote."""
    with capture_logs() as entries:
        app.dispatch(_requests(OTHER_TEAM)[request_type])

    [mismatch] = _mismatches(entries)
    assert mismatch["log_level"] == "error"
    assert mismatch["expected_team_id"] == TEAM_ID
    assert mismatch["expected_enterprise_id"] is None
    assert mismatch["received_team_id"] == OTHER_TEAM
    assert mismatch["received_enterprise_id"] is None
    assert SECRET_TEXT not in json.dumps(mismatch, default=str)
    assert RESPONSE_URL not in json.dumps(mismatch, default=str)


@pytest.mark.parametrize("request_type", REQUEST_TYPES)
def test_refused_request_gets_an_ephemeral_notice_only_where_a_response_url_exists(app: App, request_type: str) -> None:
    """The notice goes to the request's response URL, ephemeral, in both languages, with a short timeout."""
    with capture_logs():
        app.dispatch(_requests(OTHER_TEAM)[request_type])

    if request_type not in WITH_RESPONSE_URL:
        assert RecordingWebhook.sent == []
        return
    [notice] = RecordingWebhook.sent
    assert notice["url"] == RESPONSE_URL
    assert notice["timeout"] == 2
    assert notice["response_type"] == "ephemeral"
    assert "Slack" in notice["text"]
    assert "espace de travail" in notice["text"]
    assert TEAM_ID not in notice["text"]


def test_failing_notice_is_logged_and_the_request_is_still_acked(app: App) -> None:
    """A response URL that fails never changes the ack; the failure is a warning."""
    RecordingWebhook.fail = True

    with capture_logs() as entries:
        response = app.dispatch(_requests(OTHER_TEAM)["command"])

    assert response.status == 200
    failed = [entry for entry in entries if entry["event"] == "slack_tenant_notice_failed"]
    assert [entry["log_level"] for entry in failed] == ["warning"]


def test_shared_channel_event_from_an_external_user_passes(app: App, calls: list[str]) -> None:
    """An event in a Slack Connect channel names the external user's workspace, but the installation is ours: it passes."""
    with capture_logs() as entries:
        response = app.dispatch(_event(TEAM_ID, user_team=OTHER_TEAM))

    assert response.status == 200
    assert calls == ["event"]
    assert not _mismatches(entries)


def test_url_verification_is_answered_before_the_guard(app: App) -> None:
    """Slack's endpoint check carries no tenant and is answered by Bolt itself."""
    request = BoltRequest(
        body=json.dumps({"type": "url_verification", "challenge": "c0"}), headers={"content-type": ["application/json"]}
    )

    with capture_logs() as entries:
        response = app.dispatch(request)

    assert response.status == 200
    assert json.loads(response.body) == {"challenge": "c0"}
    assert not _mismatches(entries)


def test_install_without_a_tenant_fails_closed(app: App) -> None:
    """With no tenant to verify against, the guard refuses to install rather than letting every request through."""
    with pytest.raises(ValueError, match=r"\[slack.tenant\]"):
        install_slack_tenant_guard(app, None)
