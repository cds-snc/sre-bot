"""Unit tests for block-action and view-submission registration on the Slack provider.

The Bolt bootstrap and Socket Mode handler are replaced with recording fakes,
so ``initialize_app`` runs unchanged while the tests observe which listeners
it attaches to the app, and under which exact id; a value-scoped alias is
recorded with the matchers it was attached with, in attach order. Registration
errors are asserted as raised exceptions because they abort boot.
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from integrations.slack.formatter import SlackBlockKitFormatter
from integrations.slack.provider import SlackPlatformProvider

pytestmark = pytest.mark.unit


class RecordingBoltApp:
    """Records each listener attached through ``block_action``, ``attachment_action`` and ``view_submission``."""

    def __init__(self) -> None:
        self.client = object()
        self.block_actions: dict[str, Callable[..., object]] = {}
        self.view_submissions: dict[str, Callable[..., object]] = {}
        self.attachment_actions: dict[str, Callable[..., object]] = {}
        self.scoped_attachment_actions: list[tuple[str, Callable[..., object], list[Callable[..., bool]]]] = []
        self.attach_order: list[str] = []

    def command(self, command: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        return lambda listener: listener

    def block_action(self, action_id: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def attach(listener: Callable[..., object]) -> Callable[..., object]:
            self.block_actions[action_id] = listener
            return listener

        return attach

    def attachment_action(
        self, callback_id: str, matchers: list[Callable[..., bool]] | None = None
    ) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def attach(listener: Callable[..., object]) -> Callable[..., object]:
            if matchers:
                self.scoped_attachment_actions.append((callback_id, listener, matchers))
            else:
                self.attachment_actions[callback_id] = listener
            self.attach_order.append(callback_id)
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
    monkeypatch.setattr("integrations.slack.provider.LegacySlackBootstrap", lambda: SimpleNamespace(create_app=lambda **_: app))
    monkeypatch.setattr("integrations.slack.provider.SocketModeHandler", lambda app, token, logger=None: SimpleNamespace(app=app))
    return app


@pytest.fixture
def provider() -> SlackPlatformProvider:
    settings = SimpleNamespace(app_token=SecretStr("xapp-test"), bot_token=SecretStr("xoxb-test"))
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


def test_aliases_attach_the_same_listener_under_each_id(provider: SlackPlatformProvider, bolt_app: RecordingBoltApp) -> None:
    provider.register_block_action("demo.feature.approve", approve, legacy_action_ids=("approve_legacy",))
    provider.register_attachment_action("demo.feature.alert", submit, legacy_callback_ids=("alert_legacy",))

    provider.initialize_app()

    assert bolt_app.block_actions == {"demo.feature.approve": approve, "approve_legacy": approve}
    assert bolt_app.attachment_actions == {"demo.feature.alert": submit, "alert_legacy": submit}


def test_an_attachment_action_may_share_an_id_with_a_view(provider: SlackPlatformProvider, bolt_app: RecordingBoltApp) -> None:
    provider.register_attachment_action("demo.feature.edit", approve)
    provider.register_view_submission("demo.feature.edit", submit)

    provider.initialize_app()

    assert bolt_app.attachment_actions == {"demo.feature.edit": approve}
    assert bolt_app.view_submissions == {"demo.feature.edit": submit}


def clicked(value: str | None) -> dict[str, Any]:
    action: dict[str, Any] = {"name": "button", "type": "button"}
    if value is not None:
        action["value"] = value
    return {"type": "interactive_message", "callback_id": "posted_legacy", "actions": [action]}


def test_scoped_aliases_attach_after_the_exact_ids_with_a_value_matcher(
    provider: SlackPlatformProvider, bolt_app: RecordingBoltApp
) -> None:
    provider.register_attachment_action("demo.feature.archive", approve, legacy_callback_values={"posted_legacy": ("archive",)})
    provider.register_attachment_action("demo.feature.alert", submit, legacy_callback_ids=("alert_legacy",))

    provider.initialize_app()

    assert bolt_app.attachment_actions == {"demo.feature.archive": approve, "demo.feature.alert": submit, "alert_legacy": submit}
    assert bolt_app.attach_order[-1] == "posted_legacy"
    [(callback_id, listener, matchers)] = bolt_app.scoped_attachment_actions
    assert (callback_id, listener) == ("posted_legacy", approve)
    assert [all(matcher(body=clicked(value)) for matcher in matchers) for value in ("archive", "ignore", None)] == [
        True,
        False,
        False,
    ]


def test_a_value_claimed_twice_for_one_callback_raises(provider: SlackPlatformProvider) -> None:
    provider.register_attachment_action("demo.one.archive", approve, legacy_callback_values={"posted_legacy": ("archive",)})

    with pytest.raises(ValueError, match="archive"):
        provider.register_attachment_action(
            "demo.two.archive", submit, legacy_callback_values={"posted_legacy": ("ignore", "archive")}
        )


def test_disjoint_values_on_one_callback_may_belong_to_different_listeners(provider: SlackPlatformProvider) -> None:
    provider.register_attachment_action("demo.one.archive", approve, legacy_callback_values={"posted_legacy": ("archive",)})
    provider.register_attachment_action("demo.two.schedule", submit, legacy_callback_values={"posted_legacy": ("schedule",)})

    assert provider.legacy_callback_values() == {
        ("posted_legacy", "archive"): "demo.one.archive",
        ("posted_legacy", "schedule"): "demo.two.schedule",
    }


def test_a_scoped_callback_id_that_is_an_exact_id_raises(provider: SlackPlatformProvider) -> None:
    provider.register_attachment_action("demo.feature.alert", approve, legacy_callback_ids=("posted_legacy",))

    with pytest.raises(ValueError, match="posted_legacy"):
        provider.register_attachment_action(
            "demo.feature.archive", submit, legacy_callback_values={"posted_legacy": ("archive",)}
        )


def test_an_exact_id_that_is_a_scoped_callback_id_raises(provider: SlackPlatformProvider) -> None:
    provider.register_attachment_action("demo.feature.archive", submit, legacy_callback_values={"posted_legacy": ("archive",)})

    with pytest.raises(ValueError, match="posted_legacy"):
        provider.register_block_action("demo.feature.approve", approve, legacy_action_ids=("posted_legacy",))


def test_a_refused_scoped_registration_stores_none_of_its_ids(provider: SlackPlatformProvider) -> None:
    provider.register_attachment_action("demo.one.archive", approve, legacy_callback_values={"posted_legacy": ("archive",)})

    with pytest.raises(ValueError):
        provider.register_attachment_action(
            "demo.two.alert", submit, legacy_callback_values={"other_legacy": ("x",), "posted_legacy": ("archive",)}
        )

    assert provider.legacy_callback_values() == {("posted_legacy", "archive"): "demo.one.archive"}
    provider.register_attachment_action("demo.two.alert", submit, legacy_callback_values={"other_legacy": ("x",)})


@pytest.mark.parametrize(
    "values", [{"": ("archive",)}, {"posted_legacy": ("",)}, {"posted_legacy": ()}, {"posted_legacy": "archive"}]
)
def test_a_blank_empty_or_string_scope_raises(provider: SlackPlatformProvider, values: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        provider.register_attachment_action("demo.feature.archive", approve, legacy_callback_values=values)
