"""Unit tests for block-action and view-submission registration on the Slack provider.

The Bolt bootstrap and Socket Mode handler are replaced with recording fakes,
so ``initialize_app`` runs unchanged while the tests observe which listeners
it attaches to the app, and under which exact id. Registration errors are
asserted as raised exceptions because they abort boot.
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider

pytestmark = pytest.mark.unit


class RecordingBoltApp:
    """Records each listener attached through ``block_action`` and ``view_submission``."""

    def __init__(self) -> None:
        self.client = object()
        self.block_actions: dict[str, Callable[..., object]] = {}
        self.view_submissions: dict[str, Callable[..., object]] = {}

    def command(self, command: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        return lambda listener: listener

    def block_action(self, action_id: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def attach(listener: Callable[..., object]) -> Callable[..., object]:
            self.block_actions[action_id] = listener
            return listener

        return attach

    def view_submission(self, callback_id: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def attach(listener: Callable[..., object]) -> Callable[..., object]:
            self.view_submissions[callback_id] = listener
            return listener

        return attach


@pytest.fixture
def bolt_app(monkeypatch: pytest.MonkeyPatch) -> RecordingBoltApp:
    app = RecordingBoltApp()
    monkeypatch.setattr("integrations.slack.provider.LegacySlackBootstrap", lambda: SimpleNamespace(create_app=lambda: app))
    monkeypatch.setattr("integrations.slack.provider.SocketModeHandler", lambda app, token: SimpleNamespace(app=app))
    return app


@pytest.fixture
def provider() -> SlackPlatformProvider:
    settings = SimpleNamespace(ENABLED=True, SOCKET_MODE=True, APP_TOKEN="xapp-test", BOT_TOKEN="xoxb-test")
    return SlackPlatformProvider(settings=settings, formatter=SlackBlockKitFormatter())


def approve(**_: Any) -> None:
    """Stand-in block-action listener."""


def submit(**_: Any) -> None:
    """Stand-in view-submission listener."""


def test_initialize_app_attaches_registered_listeners_by_exact_id(
    provider: SlackPlatformProvider, bolt_app: RecordingBoltApp
) -> None:
    provider.register_block_action("demo.feature.approve", approve)
    provider.register_view_submission("demo.feature.submit", submit)

    result = provider.initialize_app()

    assert result.is_success
    assert bolt_app.block_actions == {"demo.feature.approve": approve}
    assert bolt_app.view_submissions == {"demo.feature.submit": submit}


def test_listeners_reach_bolt_unwrapped(provider: SlackPlatformProvider, bolt_app: RecordingBoltApp) -> None:
    provider.register_block_action("demo.feature.approve", approve)

    provider.initialize_app()

    assert bolt_app.block_actions["demo.feature.approve"] is approve


def test_duplicate_action_id_raises(provider: SlackPlatformProvider) -> None:
    provider.register_block_action("demo.feature.approve", approve)

    with pytest.raises(ValueError, match="demo.feature.approve"):
        provider.register_block_action("demo.feature.approve", submit)


def test_duplicate_callback_id_raises(provider: SlackPlatformProvider) -> None:
    provider.register_view_submission("demo.feature.submit", submit)

    with pytest.raises(ValueError, match="demo.feature.submit"):
        provider.register_view_submission("demo.feature.submit", approve)


def test_same_id_may_name_an_action_and_a_view(provider: SlackPlatformProvider, bolt_app: RecordingBoltApp) -> None:
    provider.register_block_action("demo.feature.edit", approve)
    provider.register_view_submission("demo.feature.edit", submit)

    provider.initialize_app()

    assert bolt_app.block_actions == {"demo.feature.edit": approve}
    assert bolt_app.view_submissions == {"demo.feature.edit": submit}


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_ids_raise(provider: SlackPlatformProvider, blank: str) -> None:
    with pytest.raises(ValueError):
        provider.register_block_action(blank, approve)
    with pytest.raises(ValueError):
        provider.register_view_submission(blank, submit)


def test_registration_after_listeners_are_attached_raises(provider: SlackPlatformProvider, bolt_app: RecordingBoltApp) -> None:
    provider.initialize_app()

    with pytest.raises(RuntimeError):
        provider.register_block_action("demo.feature.late", approve)
    with pytest.raises(RuntimeError):
        provider.register_view_submission("demo.feature.late", submit)
    assert bolt_app.block_actions == {}
    assert bolt_app.view_submissions == {}
