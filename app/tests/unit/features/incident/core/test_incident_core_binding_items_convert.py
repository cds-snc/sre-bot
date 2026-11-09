"""Behavior tests for the binding item conversion.

``binding_item`` writes the stored form of an ``IncidentBinding`` and
``parse_binding_item`` reads it back. The stored names equal the field names;
``conversation_id`` exists only on chat kinds (it is the sparse index key).
An unknown kind and an unreadable item are different refusals, because the first
is skipped and the second fails the lookup closed.
"""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.binding_items import (
    CONVERSATION_ATTRIBUTE,
    PARTITION_ATTRIBUTE,
    SORT_ATTRIBUTE,
    UnknownBindingKindError,
    UnreadableBindingItemError,
    binding_item,
    binding_key,
    parse_binding_item,
)
from features.incident.core.domain import BindingKind
from tests.factories.incident import SLACK_TENANT, binding_on

pytestmark = pytest.mark.unit

CHANNEL = "C0INCIDENT"
ARCHIVED_AT = datetime(2026, 10, 2, 8, 30, tzinfo=UTC)


def test_the_key_is_kind_system_tenant_and_vendor_id() -> None:
    key = binding_key(BindingKind.CHAT_CONVERSATION, WorkplaceSystem.SLACK, SLACK_TENANT, CHANNEL)

    assert key == f"chat_conversation#slack#{SLACK_TENANT}#{CHANNEL}"


def test_the_attribute_names_are_the_declared_table_keys() -> None:
    assert (PARTITION_ATTRIBUTE, SORT_ATTRIBUTE, CONVERSATION_ATTRIBUTE) == ("incident_id", "binding_key", "conversation_id")


def test_a_chat_binding_is_stored_under_its_field_names_with_the_conversation_id() -> None:
    item = binding_item(binding_on(CHANNEL, "inc-1"))

    assert item == {
        "incident_id": "inc-1",
        "binding_key": f"chat_conversation#slack#{SLACK_TENANT}#{CHANNEL}",
        "kind": "chat_conversation",
        "system": "slack",
        "tenant": SLACK_TENANT,
        "vendor_id": CHANNEL,
        "conversation_id": CHANNEL,
        "primary": True,
        "bound_by": "U0DECLARER",
        "bound_at": "2026-10-01T12:00:00.000000+00:00",
    }


def test_url_and_archived_at_are_stored_only_when_set() -> None:
    plain = binding_item(binding_on(CHANNEL, "inc-1"))
    full = binding_item(binding_on(CHANNEL, "inc-1", archived_at=ARCHIVED_AT))

    assert "url" not in plain
    assert "archived_at" not in plain
    assert full["archived_at"] == "2026-10-02T08:30:00.000000+00:00"


@pytest.mark.parametrize("archived_at", [None, ARCHIVED_AT])
@pytest.mark.parametrize("primary", [True, False])
def test_a_stored_binding_reads_back_equal(primary: bool, archived_at: datetime | None) -> None:
    binding = binding_on(CHANNEL, "inc-1", primary=primary, archived_at=archived_at)

    assert parse_binding_item(binding_item(binding)) == binding


def test_a_url_hint_survives_the_round_trip() -> None:
    with_url = replace(binding_on(CHANNEL, "inc-1"), url="https://example.slack.com/archives/C0INCIDENT")

    assert parse_binding_item(binding_item(with_url)) == with_url


def test_an_unknown_kind_is_named_for_the_caller_to_skip() -> None:
    item: dict[str, Any] = {**binding_item(binding_on(CHANNEL, "inc-1")), "kind": "backstage_page"}

    with pytest.raises(UnknownBindingKindError) as raised:
        parse_binding_item(item)

    assert (raised.value.incident_id, raised.value.kind) == ("inc-1", "backstage_page")


@pytest.mark.parametrize(
    "damage",
    [
        {"bound_at": None},
        {"bound_at": "yesterday"},
        {"bound_at": "2026-10-01T12:00:00"},
        {"primary": "yes"},
        {"tenant": None},
        {"system": "carrier-pigeon"},
        {"vendor_id": ""},
        {"incident_id": None},
        {"archived_at": "not a time"},
    ],
)
def test_an_item_with_a_missing_or_ill_typed_field_is_unreadable(damage: dict[str, Any]) -> None:
    item = {**binding_item(binding_on(CHANNEL, "inc-1")), **damage}
    item = {name: value for name, value in item.items() if value is not None}

    with pytest.raises(UnreadableBindingItemError):
        parse_binding_item(item)


def test_an_item_whose_stored_key_differs_from_its_fields_is_unreadable() -> None:
    item = {**binding_item(binding_on(CHANNEL, "inc-1")), "binding_key": "chat_conversation#slack#T0OTHER#C0ELSE"}

    with pytest.raises(UnreadableBindingItemError):
        parse_binding_item(item)
