"""Unit tests for the interpret stage: match, extract, render, and the event that results.

The stage runs over in-memory kinds and payloads with default limits.
"""

import pytest

from capabilities.webhooks.domain.events import EventType
from capabilities.webhooks.domain.interpret import Matched, RenderFailed, Suppressed, Unmatched, interpret
from tests.unit.capabilities.webhooks.conftest import LANGUAGES, build_kind, delivery, kind_document, limits, payload

pytestmark = pytest.mark.unit


def test_a_matching_delivery_becomes_an_event_typed_by_the_kind() -> None:
    kind = build_kind(kind_document())
    body = payload() | {"type": "notification", "event_type": "slack.passthrough"}

    result = interpret([kind], body, delivery(), languages=LANGUAGES, limits=limits())

    assert isinstance(result, Matched)
    event = result.event
    assert (event.id, event.source, event.type, event.time) == ("msg-1", "inst-1", EventType.ALERT, delivery().received_at)
    assert dict(event.data.attributes) == {  # type: ignore[union-attr]
        "budget": "sandbox",
        "spent": 120.5,
        "console": "https://console.aws.amazon.com/billing/home",
        "message": "Actual spend is over the budget.",
    }


def test_no_matching_kind_is_unmatched() -> None:
    result = interpret([build_kind(kind_document())], {"source": "other"}, delivery(), languages=LANGUAGES, limits=limits())

    assert result == Unmatched()


def test_a_suppressed_kind_posts_nothing() -> None:
    kind = build_kind(kind_document(templates=None, links=None, alert=None, suppress=True))

    assert interpret([kind], payload(), delivery(), languages=LANGUAGES, limits=limits()) == Suppressed("budget-alert")


def test_a_missing_required_field_is_a_render_failure_naming_the_field() -> None:
    body = payload()
    del body["detail"]["name"]

    result = interpret([build_kind(kind_document())], body, delivery(), languages=LANGUAGES, limits=limits())

    assert result == RenderFailed("budget-alert", "budget", "missing")


def test_a_template_failure_is_a_render_failure_naming_the_template() -> None:
    kind = build_kind(kind_document(alert={"status": "{{ fields.budget }}"}))

    result = interpret([kind], payload(), delivery(), languages=LANGUAGES, limits=limits())

    assert isinstance(result, RenderFailed) and result.field == "alert.status"
