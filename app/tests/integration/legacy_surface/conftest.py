"""Fixtures that drive Slack commands through a real slack_bolt App.

The harness registers the production ``register_slack_commands`` hookimpls
through a pluggy PluginManager onto a real ``SlackPlatformProvider`` bound to
a real ``slack_bolt.App``, then feeds form-encoded slash-command requests to
``App.dispatch``. Only the edges are faked: the Slack Web API client, the
``response_url`` webhook that Bolt's ``respond`` posts to, and each package's
backing service (patched per test).
"""

import importlib.util
from collections.abc import Callable, Iterator
from concurrent.futures import Executor, Future
from dataclasses import dataclass, field
from types import ModuleType, SimpleNamespace
from typing import Any
from urllib.parse import urlencode

import pluggy
import pytest
from slack_bolt import App, BoltRequest, BoltResponse
from slack_bolt.authorization import AuthorizeResult
from slack_sdk.webhook import WebhookClient

import modules.dev as dev_module
import modules.sre as sre_module
import packages.access.sync as access_sync_module
import packages.geolocate as geolocate_module
import packages.incident_draft as incident_draft_module
import packages.incident_summary as incident_summary_module
import packages.rant as rant_module
import packages.user_rotations as user_rotations_module
from infrastructure.plugins.specs import FeatureLifecycleSpecs
from infrastructure.slack.settings import get_slack_transport_settings
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider

SLACK_COMMAND_HOOKIMPLS: tuple[ModuleType, ...] = (
    sre_module,
    dev_module,
    rant_module,
    user_rotations_module,
    access_sync_module,
    incident_draft_module,
    incident_summary_module,
    geolocate_module,
)

USER_ID = "U0INVOKER"
CHANNEL_ID = "C0INCIDENT"
TRIGGER_ID = "trigger-123"
RESPONSE_URL = "https://hooks.slack.test/commands/response"


class InlineExecutor(Executor):
    """Runs Bolt listeners on the dispatching thread.

    Bolt acks first and then hands the listener to its executor; running it
    inline keeps that production ordering while letting assertions observe
    every side effect as soon as ``dispatch`` returns.
    """

    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Future[Any]:
        future: Future[Any] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:
            future.set_exception(exc)
        return future


class FakeSlackClient:
    """Records every Web API call and answers with canned payloads.

    Any method name is accepted; its reply comes from ``replies`` (a dict, or
    an exception to raise) and defaults to an empty ``ok`` payload.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.replies: dict[str, dict[str, Any] | Exception] = {
            "auth_test": {"ok": True, "user_id": "UBOT", "bot_id": "BBOT", "user": "sre-bot"}
        }

    def __getattr__(self, name: str) -> Callable[..., dict[str, Any]]:
        if name.startswith("_"):
            raise AttributeError(name)

        def method(**kwargs: Any) -> dict[str, Any]:
            self.calls.append((name, kwargs))
            reply = self.replies.get(name, {"ok": True})
            if isinstance(reply, Exception):
                raise reply
            return reply

        return method

    def calls_to(self, name: str) -> list[dict[str, Any]]:
        return [kwargs for called, kwargs in self.calls if called == name]


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


def _unpatched_app_init() -> Callable[..., None]:
    """Return slack_bolt's own ``App.__init__``.

    The session-wide ``pytest_configure`` hook in ``tests/conftest.py``
    replaces ``App.__init__`` with a stub that registers nothing. Executing a
    private copy of ``slack_bolt.app.app`` recovers the library's constructor
    so this harness can build a real, fully initialised App.
    """
    spec = importlib.util.find_spec("slack_bolt.app.app")
    assert spec is not None and spec.loader is not None
    pristine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pristine)
    init: Callable[..., None] = pristine.App.__init__
    return init


def _authorize_single_workspace(**_: Any) -> AuthorizeResult:
    """Static workspace authorization, so Bolt never calls ``auth.test``."""
    return AuthorizeResult(enterprise_id=None, team_id="T0TEAM", bot_token="xoxb-test", bot_id="BBOT", bot_user_id="UBOT")


def build_harness(monkeypatch: pytest.MonkeyPatch, command_prefix: str) -> SlackCommandHarness:
    """Wire the eight hookimpls onto a fresh provider and Bolt app."""
    monkeypatch.setattr(App, "__init__", _unpatched_app_init())
    client = FakeSlackClient()
    app = RecordingApp(
        authorize=_authorize_single_workspace,
        request_verification_enabled=False,
        listener_executor=InlineExecutor(),
    )
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    provider = SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter(), command_prefix=command_prefix)
    provider._app = app
    provider._client = client

    plugin_manager = pluggy.PluginManager("sre_bot")
    plugin_manager.add_hookspecs(FeatureLifecycleSpecs)
    for hookimpl_module in SLACK_COMMAND_HOOKIMPLS:
        plugin_manager.register(hookimpl_module)
    plugin_manager.hook.register_slack_commands(provider=provider)
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
