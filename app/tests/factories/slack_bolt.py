"""Edges for driving a real slack_bolt App in tests.

A test builds a real ``App`` with ``unpatched_app_init`` and
``authorize_single_workspace``, runs its listeners inline with
``InlineExecutor`` and records Web API calls with ``FakeSlackClient``.
"""

import importlib.util
from collections.abc import Callable
from concurrent.futures import Executor, Future
from typing import Any

from slack_bolt.authorization import AuthorizeResult

TEAM_ID = "T0TEAM"
BOT_TOKEN = "xoxb-test"


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
