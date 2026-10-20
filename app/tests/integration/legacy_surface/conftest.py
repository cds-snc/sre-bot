"""Fixtures that drive Slack commands and interactions through a real slack_bolt App.

``slack_command_harness`` registers the production ``register_slack_commands`` hookimpls
through a pluggy PluginManager, then the legacy sre and dev commands through
the lifespan's own ``_register_legacy_slack_commands``, onto a real
``SlackPlatformProvider`` bound to a real ``slack_bolt.App``, then feeds form-encoded slash-command requests to
``App.dispatch``. Only the edges are faked: the Slack Web API client (which
also backs each package's Slack lookup adapter), the ``response_url`` webhook
that Bolt's ``respond`` posts to, and each package's backing service (patched
per test).

``legacy_handler_harness`` registers the hard-coded legacy modules through the
lifespan's own ``_register_legacy_handlers`` on a fresh Bolt app, and feeds it
slash commands, interaction payloads and Events API callbacks. Bolt hands those
listeners a ``WebClient`` it builds per request, so ``WebClient.api_call`` is
routed into a ``FakeSlackClient``. The external edges the legacy handlers reach
are faked: ``response_url`` posts, the Sentinel ``send_event`` sender, the Drive
folder listing and the webhook acknowledged-count increment.
"""

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from types import ModuleType, SimpleNamespace
from typing import Any, cast
from urllib.parse import urlencode

import i18n  # type: ignore
import pluggy
import pytest
import structlog
from slack_bolt import App, BoltRequest, BoltResponse
from slack_sdk import WebClient
from slack_sdk.webhook import WebhookClient

import features.incident.comms as incident_comms_module
import features.incident.scribe as incident_scribe_module
import packages.access.sync as access_sync_module
import packages.geolocate as geolocate_module
import packages.rant as rant_module
import packages.user_rotations as user_rotations_module
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from features.incident.core.adapters.slack import SlackIncidentTranscriptReader
from features.incident.drive.adapters import google_drive as incident_drive
from features.incident.scribe import providers as incident_scribe_providers
from features.incident.scribe import service as incident_scribe_service
from features.incident.scribe.adapters.slack import SlackIncidentReportLinkLookup
from infrastructure.slack.settings import get_slack_transport_settings
from integrations.sentinel import client as sentinel_client
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from integrations.slack.settings import SlackSettings
from modules.slack import webhooks as legacy_webhooks
from packages.rant.adapters.slack import SlackUserIdentityLookup
from packages.rant.platforms import slack as rant_slack
from server.lifespan import _register_legacy_handlers, _register_legacy_slack_commands
from tests.factories.incident import incident_scopes
from tests.factories.slack_bolt import FakeSlackClient, InlineExecutor, authorize_single_workspace, unpatched_app_init

SLACK_COMMAND_HOOKIMPLS: tuple[ModuleType, ...] = (
    rant_module,
    user_rotations_module,
    access_sync_module,
    incident_scribe_module,
    incident_comms_module,
    geolocate_module,
)

USER_ID = "U0INVOKER"
CHANNEL_ID = "C0INCIDENT"
TRIGGER_ID = "trigger-123"
TEAM_ID = "T0TEAM"
RESPONSE_URL = "https://hooks.slack.test/commands/response"


INCIDENT_FOLDERS: tuple[dict[str, str], ...] = (
    {"id": "F0PLATFORM", "name": "Platform"},
    {"id": "F0FORMS", "name": "Forms"},
)


class RecordingApp(App):
    """Unmodified Bolt App that also records each listener it registers.

    Slash commands land in ``registered_commands``; actions, views and events
    land in ``registered_listeners`` as ``(kind, id, has_matchers)``.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.registered_commands: list[str] = []
        self.registered_listeners: list[tuple[str, str, bool]] = []

    def command(self, command: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_commands.append(str(command))
        return super().command(command, *args, **kwargs)

    def action(self, constraints: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_listeners.append(("action", str(constraints), bool(kwargs.get("matchers"))))
        return super().action(constraints, *args, **kwargs)

    def view(self, constraints: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_listeners.append(("view", str(constraints), bool(kwargs.get("matchers"))))
        return super().view(constraints, *args, **kwargs)

    def event(self, event: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_listeners.append(("event", str(event), bool(kwargs.get("matchers"))))
        return super().event(event, *args, **kwargs)


@dataclass
class SlackCommandHarness:
    """A Bolt app with the command hookimpls registered, plus captured output."""

    app: RecordingApp
    provider: SlackPlatformProvider
    client: FakeSlackClient
    command_prefix: str
    responses: list[dict[str, Any]] = field(default_factory=list)

    def dispatch(self, command: str, text: str = "") -> BoltResponse:
        """Send one slash command through ``App.dispatch`` as Slack would."""
        body = urlencode(
            {
                "command": f"/{self.command_prefix}{command}",
                "text": text,
                "user_id": USER_ID,
                "channel_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "trigger_id": TRIGGER_ID,
                "response_url": RESPONSE_URL,
            }
        )
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)


def build_bolt_app(monkeypatch: pytest.MonkeyPatch) -> RecordingApp:
    """A real Bolt app that authorizes one workspace and runs its listeners inline."""
    monkeypatch.setattr(App, "__init__", unpatched_app_init())
    return RecordingApp(
        authorize=authorize_single_workspace,
        request_verification_enabled=False,
        listener_executor=InlineExecutor(),
    )


def capture_response_url_posts(monkeypatch: pytest.MonkeyPatch, responses: list[dict[str, Any]]) -> None:
    """Record each message Bolt's ``respond`` posts to a ``response_url`` instead of sending it."""

    def capture_send_dict(webhook: WebhookClient, body: dict[str, Any], headers: dict[str, str] | None = None) -> SimpleNamespace:
        responses.append({"url": webhook.url, **body})
        return SimpleNamespace(status_code=200, body="ok")

    monkeypatch.setattr(WebhookClient, "send_dict", capture_send_dict)


def build_harness(monkeypatch: pytest.MonkeyPatch, command_prefix: str) -> SlackCommandHarness:
    """Wire the six hookimpls and the legacy sre and dev commands onto a fresh provider and Bolt app."""
    client = FakeSlackClient()
    app = build_bolt_app(monkeypatch)
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    provider = SlackPlatformProvider(
        settings=cast(SlackSettings, settings), formatter=SlackBlockKitFormatter(), command_prefix=command_prefix
    )
    provider._app = app
    provider._client = client
    provider.set_scope_opener(incident_scopes())

    # Each package's Slack lookups run through its real adapter over the same fake client.
    web_client = cast(WebClient, client)
    monkeypatch.setattr(rant_slack, "get_user_identity_lookup", lambda: SlackUserIdentityLookup(web_client))
    monkeypatch.setattr(
        incident_scribe_service, "get_incident_transcript_reader", lambda: SlackIncidentTranscriptReader(web_client)
    )
    monkeypatch.setattr(
        incident_scribe_providers, "get_incident_report_link_lookup", lambda: SlackIncidentReportLinkLookup(web_client)
    )

    plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    plugin_manager.add_hookspecs(FeatureLifecycleSpecs)
    for hookimpl_module in SLACK_COMMAND_HOOKIMPLS:
        plugin_manager.register(hookimpl_module)
    plugin_manager.hook.register_slack_commands(registrar=provider)
    _register_legacy_slack_commands(provider, structlog.get_logger())
    provider._auto_register_root_commands()

    harness = SlackCommandHarness(app=app, provider=provider, client=client, command_prefix=command_prefix)
    capture_response_url_posts(monkeypatch, harness.responses)
    return harness


@pytest.fixture
def slack_command_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[SlackCommandHarness]:
    """Harness using the deployment's configured slash-command prefix."""
    yield build_harness(monkeypatch, get_slack_transport_settings().COMMAND_PREFIX)


@dataclass
class LegacyHandlerHarness:
    """A Bolt app with the hard-coded legacy handlers registered, plus captured edges."""

    app: RecordingApp
    client: FakeSlackClient
    command_prefix: str
    sentinel_events: list[dict[str, Any]] = field(default_factory=list)
    acknowledged_webhooks: list[str] = field(default_factory=list)
    responses: list[dict[str, Any]] = field(default_factory=list)

    def command(self, command: str, text: str = "") -> BoltResponse:
        """Send one slash command through ``App.dispatch`` as Slack would."""
        body = urlencode(
            {
                "command": f"/{self.command_prefix}{command}",
                "text": text,
                "user_id": USER_ID,
                "channel_id": CHANNEL_ID,
                "team_id": TEAM_ID,
                "trigger_id": TRIGGER_ID,
                "response_url": RESPONSE_URL,
            }
        )
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)

    def interaction(self, payload: dict[str, Any]) -> BoltResponse:
        """Send a block_actions, interactive_message or view_submission payload as Slack would."""
        body = urlencode({"payload": json.dumps({"team": {"id": TEAM_ID}, "user": {"id": USER_ID}, **payload})})
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)

    def event(self, event: dict[str, Any]) -> BoltResponse:
        """Send one Events API callback wrapping ``event`` as Slack would."""
        body = json.dumps({"type": "event_callback", "team_id": TEAM_ID, "event_id": "Ev0TEST", "event": event})
        request = BoltRequest(body=body, headers={"content-type": ["application/json"]})
        return self.app.dispatch(request)


@pytest.fixture
def legacy_handler_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[LegacyHandlerHarness]:
    """Bolt app with ``_register_legacy_handlers`` applied and every external edge faked.

    Listener-injected Web API clients reach the harness's ``FakeSlackClient``
    by method name (``views.open`` -> ``views_open``), with canned replies for
    the lookups the legacy handlers index into. The global i18n locale is
    restored afterwards because the legacy handlers set it per request.
    """
    client = FakeSlackClient()
    client.replies["users_info"] = {"ok": True, "user": {"id": USER_ID, "locale": "en-US"}}
    client.replies["conversations_create"] = {"ok": True, "channel": {"id": "C0NEWINCIDENT"}}
    app = build_bolt_app(monkeypatch)
    harness = LegacyHandlerHarness(app=app, client=client, command_prefix=get_slack_transport_settings().COMMAND_PREFIX)

    def route_api_call(web_client: WebClient, api_method: str, **kwargs: Any) -> Any:
        arguments = kwargs.get("json") or kwargs.get("params") or kwargs.get("data") or {}
        # The SDK strips unset optional arguments before sending; so does the router.
        sent = {name: value for name, value in arguments.items() if value is not None}
        return getattr(client, api_method.replace(".", "_"))(**sent)

    def record_sentinel_event(payload: dict[str, Any]) -> bool:
        harness.sentinel_events.append(payload)
        return True

    monkeypatch.setattr(WebClient, "api_call", route_api_call)
    capture_response_url_posts(monkeypatch, harness.responses)
    monkeypatch.setattr(sentinel_client, "send_event", record_sentinel_event)
    monkeypatch.setattr(incident_drive, "list_child_folders", lambda parent_folder_id: [dict(f) for f in INCIDENT_FOLDERS])
    monkeypatch.setattr(legacy_webhooks, "increment_acknowledged_count", harness.acknowledged_webhooks.append)

    _register_legacy_handlers(app, structlog.get_logger())
    locale, fallback = i18n.get("locale"), i18n.get("fallback")
    yield harness
    i18n.set("locale", locale)
    i18n.set("fallback", fallback)
