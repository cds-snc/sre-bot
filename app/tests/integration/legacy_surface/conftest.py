"""Fixtures that drive Slack commands through a real slack_bolt App.

The harness registers the production ``register_slack_commands`` hookimpls
through a pluggy PluginManager, then the legacy sre and dev commands through
the lifespan's own ``_register_legacy_slack_commands``, onto a real
``SlackPlatformProvider`` bound to a real ``slack_bolt.App``, then feeds form-encoded slash-command requests to
``App.dispatch``. Only the edges are faked: the Slack Web API client (which
also backs each package's Slack lookup adapter), the ``response_url`` webhook
that Bolt's ``respond`` posts to, and each package's backing service (patched
per test).
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from types import ModuleType, SimpleNamespace
from typing import Any
from urllib.parse import urlencode

import pluggy
import pytest
import structlog
from slack_bolt import App, BoltRequest, BoltResponse
from slack_sdk.webhook import WebhookClient

import features.incident.scribe as incident_scribe_module
import packages.access.sync as access_sync_module
import packages.geolocate as geolocate_module
import packages.rant as rant_module
import packages.user_rotations as user_rotations_module
from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from features.incident.core.adapters.slack import SlackIncidentTranscriptReader
from features.incident.scribe import providers as incident_scribe_providers
from features.incident.scribe import service as incident_scribe_service
from features.incident.scribe.adapters.slack import SlackIncidentReportLinkLookup
from infrastructure.slack.settings import get_slack_transport_settings
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from packages.rant.adapters.slack import SlackUserIdentityLookup
from packages.rant.platforms import slack as rant_slack
from server.lifespan import _register_legacy_slack_commands
from tests.factories.slack_bolt import FakeSlackClient, InlineExecutor, authorize_single_workspace, unpatched_app_init

SLACK_COMMAND_HOOKIMPLS: tuple[ModuleType, ...] = (
    rant_module,
    user_rotations_module,
    access_sync_module,
    incident_scribe_module,
    geolocate_module,
)

USER_ID = "U0INVOKER"
CHANNEL_ID = "C0INCIDENT"
TRIGGER_ID = "trigger-123"
RESPONSE_URL = "https://hooks.slack.test/commands/response"


class RecordingApp(App):
    """Unmodified Bolt App that also records each slash command it registers."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.registered_commands: list[str] = []

    def command(self, command: Any, *args: Any, **kwargs: Any) -> Any:
        self.registered_commands.append(str(command))
        return super().command(command, *args, **kwargs)


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
                "team_id": "T0TEAM",
                "trigger_id": TRIGGER_ID,
                "response_url": RESPONSE_URL,
            }
        )
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)


def build_harness(monkeypatch: pytest.MonkeyPatch, command_prefix: str) -> SlackCommandHarness:
    """Wire the five hookimpls and the legacy sre and dev commands onto a fresh provider and Bolt app."""
    monkeypatch.setattr(App, "__init__", unpatched_app_init())
    client = FakeSlackClient()
    app = RecordingApp(
        authorize=authorize_single_workspace,
        request_verification_enabled=False,
        listener_executor=InlineExecutor(),
    )
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    provider = SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter(), command_prefix=command_prefix)
    provider._app = app
    provider._client = client

    # Each package's Slack lookups run through its real adapter over the same fake client.
    monkeypatch.setattr(rant_slack, "get_user_identity_lookup", lambda: SlackUserIdentityLookup(client))
    monkeypatch.setattr(incident_scribe_service, "get_incident_transcript_reader", lambda: SlackIncidentTranscriptReader(client))
    monkeypatch.setattr(
        incident_scribe_providers, "get_incident_report_link_lookup", lambda: SlackIncidentReportLinkLookup(client)
    )

    plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
    plugin_manager.add_hookspecs(FeatureLifecycleSpecs)
    for hookimpl_module in SLACK_COMMAND_HOOKIMPLS:
        plugin_manager.register(hookimpl_module)
    plugin_manager.hook.register_slack_commands(registrar=provider)
    _register_legacy_slack_commands(provider, structlog.get_logger())
    provider._auto_register_root_commands()

    harness = SlackCommandHarness(app=app, provider=provider, client=client, command_prefix=command_prefix)

    def capture_send_dict(webhook: WebhookClient, body: dict[str, Any], headers: dict[str, str] | None = None) -> SimpleNamespace:
        harness.responses.append({"url": webhook.url, **body})
        return SimpleNamespace(status_code=200, body="ok")

    monkeypatch.setattr(WebhookClient, "send_dict", capture_send_dict)
    return harness


@pytest.fixture
def slack_command_harness(monkeypatch: pytest.MonkeyPatch) -> Iterator[SlackCommandHarness]:
    """Harness using the deployment's configured slash-command prefix."""
    yield build_harness(monkeypatch, get_slack_transport_settings().COMMAND_PREFIX)
