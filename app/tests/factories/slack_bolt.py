"""Edges for driving a real slack_bolt App in tests.

A test builds a real ``App`` with ``unpatched_app_init`` and
``authorize_single_workspace``, runs its listeners inline with
``InlineExecutor`` and records Web API calls with ``FakeSlackClient``.
"""

import importlib.util
import json
from collections.abc import Callable, Iterator
from concurrent.futures import Executor, Future
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from urllib.parse import urlencode

import pluggy
import pytest
from slack_bolt import App, BoltRequest, BoltResponse
from slack_bolt.authorization import AuthorizeResult
from slack_sdk import WebClient

from contracts.plugins.hookspecs import FeatureLifecycleSpecs
from contracts.plugins.namespace import PLUGIN_NAMESPACE
from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider
from server.plugins.manager import register_feature_integrations

TEAM_ID = "T0TEAM"
BOT_TOKEN = "xoxb-test"
USER_ID = "U0APPROVER"
TRIGGER_ID = "trigger-456"


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
            "auth_test": {"ok": True, "user_id": "UBOT", "bot_id": "BBOT", "user": "sre-bot"},
            "views_open": {"ok": True, "view": {"id": "VFAKE"}},
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


def unpatched_app_init() -> Callable[..., None]:
    """Return slack_bolt's own ``App.__init__``.

    The session-wide ``pytest_configure`` hook in ``tests/conftest.py``
    replaces ``App.__init__`` with a stub that registers nothing. Executing a
    private copy of ``slack_bolt.app.app`` recovers the library's constructor
    so a test can build a real, fully initialised App.
    """
    spec = importlib.util.find_spec("slack_bolt.app.app")
    assert spec is not None and spec.loader is not None
    pristine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pristine)
    init: Callable[..., None] = pristine.App.__init__
    return init


def authorize_single_workspace(**_: Any) -> AuthorizeResult:
    """Static workspace authorization, so Bolt never calls ``auth.test``."""
    return AuthorizeResult(enterprise_id=None, team_id=TEAM_ID, bot_token=BOT_TOKEN, bot_id="BBOT", bot_user_id="UBOT")


@dataclass
class Harness:
    """Drives a real Bolt app with a plugin registered on a real pluggy PluginManager.

    The app's listeners run inline, and WebClient.api_call is stubbed to record
    calls without network access. Slack payloads are form-encoded as real requests.
    """

    app: App
    plugin: Any
    api_calls: list[tuple[str, dict[str, Any]]]

    def dispatch(self, payload: dict[str, Any]) -> BoltResponse:
        """Dispatch a payload as a form-encoded Slack request.

        Args:
            payload: The block_actions or view_submission payload.

        Returns:
            The Bolt app's response.
        """
        body = urlencode({"payload": json.dumps({"team": {"id": TEAM_ID}, "user": {"id": USER_ID}, **payload})})
        request = BoltRequest(body=body, headers={"content-type": ["application/x-www-form-urlencoded"]})
        return self.app.dispatch(request)


def harness_fixture(
    plugin_name: str,
) -> Callable[[pytest.MonkeyPatch, Any], Iterator[Harness]]:
    """Build a pytest fixture factory for a Slack Bolt app with a plugin.

    The fixture registers the plugin on a real pluggy PluginManager with the
    given name, creates a real SlackPlatformProvider, registers feature
    integrations, and yields a Harness for dispatching payloads.

    Args:
        plugin_name: The dotted entry-point name for the plugin (e.g. ``incident.scribe``).

    Returns:
        A pytest fixture function that accepts monkeypatch and yields a Harness.
    """

    def fixture(monkeypatch: pytest.MonkeyPatch, plugin: Any) -> Iterator[Harness]:
        monkeypatch.setattr(App, "__init__", unpatched_app_init())
        api_calls: list[tuple[str, dict[str, Any]]] = []

        def record_api_call(self: WebClient, api_method: str, **kwargs: Any) -> dict[str, Any]:
            api_calls.append((api_method, kwargs.get("json") or kwargs.get("params") or {}))
            return {"ok": True}

        monkeypatch.setattr(WebClient, "api_call", record_api_call)

        plugin_manager = pluggy.PluginManager(PLUGIN_NAMESPACE)
        plugin_manager.add_hookspecs(FeatureLifecycleSpecs)
        plugin_manager.register(plugin, name=plugin_name)
        monkeypatch.setattr("server.plugins.manager.get_plugin_manager", lambda: plugin_manager)

        app = App(authorize=authorize_single_workspace, request_verification_enabled=False, listener_executor=InlineExecutor())
        settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
        provider = SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter())
        monkeypatch.setattr("integrations.slack.provider.LegacySlackBootstrap", lambda: SimpleNamespace(create_app=lambda: app))
        monkeypatch.setattr("integrations.slack.provider.SocketModeHandler", lambda app, token: SimpleNamespace(app=app))

        register_feature_integrations(app=MagicMock(), logger=MagicMock(), slack_provider=provider)
        assert provider.initialize_app().is_success

        yield Harness(app=app, plugin=plugin, api_calls=api_calls)

    return fixture
