"""Unit tests for gathering consumer actions onto a posted event.

A click on an action reaches whichever plugin handles its id, so an action id must start
with the contributing plugin's entry-point name. Stub strategy: consumers are plain test
objects held directly in ``WebhookExtensions``; structlog's ``capture_logs`` records the drop.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from structlog.testing import capture_logs

from capabilities.webhooks.api import Alert, EventAction, EventContext, EventType, InboundEvent, Notification
from capabilities.webhooks.service import RegisteredConsumer, WebhookExtensions
from contracts.languages import MultilingualText

pytestmark = pytest.mark.unit

LABEL = MultilingualText((("en-US", "Call incident"), ("fr-FR", "Déclarer un incident")))


class _Offers:
    def __init__(self, *action_ids: str) -> None:
        self.event_types = frozenset({EventType.ALERT})
        self.action_ids = action_ids
        self.languages: list[Sequence[str]] = []

    def actions(self, event: InboundEvent, languages: Sequence[str]) -> tuple[EventAction, ...]:
        self.languages.append(languages)
        return tuple(EventAction(action_id=action_id, value="inst-1:item-1", label=LABEL) for action_id in self.action_ids)

    async def consume(self, event: InboundEvent, context: EventContext) -> None:
        return None


def _event() -> InboundEvent:
    text = MultilingualText((("en-US", "t"),))
    return InboundEvent(
        id="msg-1",
        source="inst-1",
        type=EventType.ALERT,
        time=datetime(2026, 11, 26, tzinfo=UTC),
        data=Alert(title=text, summary=text),
    )


def _extensions(*registered: RegisteredConsumer) -> WebhookExtensions:
    return WebhookExtensions(consumers={EventType.ALERT: registered}, handlers={}, service_scopes=object())  # type: ignore[arg-type]


def test_actions_in_the_plugins_namespace_are_gathered_in_load_order() -> None:
    first, second = _Offers("incident.response.call"), _Offers("audit.mark")

    actions = _extensions(RegisteredConsumer("incident.response", first), RegisteredConsumer("audit", second)).actions_for(
        _event(), ("en-US", "fr-FR")
    )

    assert [action.action_id for action in actions] == ["incident.response.call", "audit.mark"]
    assert first.languages == [("en-US", "fr-FR")]


def test_an_action_outside_its_plugins_namespace_is_dropped_and_logged_without_its_value() -> None:
    """A consumer cannot offer a button that another feature's handler would act on."""
    rogue = _Offers("access.request.approve", "rogue.ok")

    with capture_logs() as events:
        actions = _extensions(RegisteredConsumer("rogue", rogue)).actions_for(_event(), ("en-US",))

    assert [action.action_id for action in actions] == ["rogue.ok"]
    dropped = [event for event in events if event["event"] == "webhook_action_dropped"]
    assert dropped == [
        {"event": "webhook_action_dropped", "plugin": "rogue", "reason": "outside_namespace", "log_level": "warning"}
    ]


def test_a_prefix_without_the_dot_is_not_the_namespace() -> None:
    """``rogueish.x`` does not belong to plugin ``rogue``."""
    assert _extensions(RegisteredConsumer("rogue", _Offers("rogueish.x"))).actions_for(_event(), ("en-US",)) == ()


def test_an_action_needs_an_id_and_a_value() -> None:
    with pytest.raises(ValueError):
        EventAction(action_id="", value="v", label=LABEL)


def test_a_notification_has_no_consumers_unless_registered_for_it() -> None:
    event = InboundEvent(
        id="m",
        source="i",
        type=EventType.NOTIFICATION,
        time=datetime(2026, 11, 26, tzinfo=UTC),
        data=Notification(title=LABEL, summary=LABEL),
    )

    assert (
        _extensions(RegisteredConsumer("incident.response", _Offers("incident.response.call"))).actions_for(event, ("en-US",))
        == ()
    )
