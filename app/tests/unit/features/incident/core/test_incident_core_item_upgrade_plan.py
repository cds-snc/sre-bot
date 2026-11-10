"""Behavior tests for plan_item_upgrade, the pure per-item upgrade plan.

Items are plain dicts built by the shared legacy and end-state item factories;
no store is involved. The plan must give the binding of the item's conversation,
the guarded changes with the version marker last, and never carry a stored value
in an unreadable result except an unmatched status.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from contracts.records import SetAttribute
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.incident_items import END_STATE_VERSION, OPEN_BUCKET, RECORD_VERSION
from features.incident.core.adapters.item_upgrade import ItemUpgrade, UnboundOpenItem, plan_item_upgrade
from features.incident.core.adapters.legacy_items import UnreadableLegacyItem
from features.incident.core.domain import BindingKind
from tests.factories.incident import SLACK_TENANT
from tests.factories.legacy_upgrade import TENANTS, end_state_item, legacy_item

pytestmark = pytest.mark.unit

DECLARED_AT = datetime(2025, 10, 15, 14, 0, tzinfo=UTC)


def _upgrade(item: dict[str, Any]) -> ItemUpgrade:
    planned = plan_item_upgrade(item, TENANTS)
    assert isinstance(planned, ItemUpgrade)
    return planned


def _set(planned: ItemUpgrade) -> dict[str, Any]:
    return {change.attribute: change.value for change in planned.changes if isinstance(change, SetAttribute)}


def test_a_legacy_open_item_gets_the_primary_binding_of_its_conversation_by_its_declarer() -> None:
    planned = _upgrade(legacy_item("inc-1"))

    binding = planned.binding
    assert binding is not None
    assert (binding.incident_id, binding.kind, binding.system) == ("inc-1", BindingKind.CHAT_CONVERSATION, WorkplaceSystem.SLACK)
    assert (binding.tenant, binding.vendor_id, binding.primary) == (SLACK_TENANT, "C0INC-1", True)
    assert (binding.bound_by, binding.bound_at, binding.url) == ("U0DECLARER", DECLARED_AT, None)


def test_a_legacy_open_item_is_marked_and_put_on_the_open_index_with_the_marker_last() -> None:
    planned = _upgrade(legacy_item("inc-1"))

    values = _set(planned)
    assert planned.from_version is None
    assert (values["record_version"], values["open_bucket"], values["opened_at"]) == (
        RECORD_VERSION,
        OPEN_BUCKET,
        values["declared_at"],
    )
    assert planned.changes[-1] == SetAttribute("record_version", RECORD_VERSION)
    assert planned.expected["record_version"] is None


def test_a_legacy_closed_item_with_a_conversation_gets_a_binding_and_no_open_index() -> None:
    planned = _upgrade(legacy_item("inc-1", status="Closed"))

    assert planned.binding is not None
    assert {"open_bucket", "opened_at"}.isdisjoint(_set(planned))


def test_a_legacy_closed_item_without_a_conversation_is_raised_with_no_binding() -> None:
    planned = _upgrade(legacy_item("inc-1", status="Closed", channel_id=None))

    assert planned.binding is None
    assert _set(planned)["record_version"] == RECORD_VERSION


@pytest.mark.parametrize("channel_id", [None, " "])
def test_a_legacy_open_item_without_a_conversation_is_unbound(channel_id: str | None) -> None:
    planned = plan_item_upgrade(legacy_item("inc-1", channel_id=channel_id), TENANTS)

    assert planned == UnboundOpenItem("inc-1")


def test_a_version_one_open_item_gets_its_binding_and_exactly_the_raise() -> None:
    planned = _upgrade(end_state_item("inc-1"))

    assert planned.from_version == END_STATE_VERSION
    assert planned.binding is not None and planned.binding.vendor_id == "C0INC-1"
    assert planned.changes == (SetAttribute("record_version", RECORD_VERSION),)
    assert planned.expected["record_version"] == END_STATE_VERSION
    assert set(planned.expected) == {"record_version", "channel_id", "status", "declared_at"}


def test_a_version_one_closed_item_gets_its_binding() -> None:
    planned = _upgrade(end_state_item("inc-1", status="Closed"))

    assert planned.binding is not None
    assert planned.changes == (SetAttribute("record_version", RECORD_VERSION),)


def test_a_version_one_item_without_a_conversation_is_unbound_when_open_and_unbinding_when_closed() -> None:
    open_item = end_state_item("inc-1", conversation=None)
    closed_item = end_state_item("inc-2", conversation=None, status="Closed")

    assert plan_item_upgrade(open_item, TENANTS) == UnboundOpenItem("inc-1")
    assert _upgrade(closed_item).binding is None


@pytest.mark.parametrize("version", [RECORD_VERSION, RECORD_VERSION + 1, Decimal(RECORD_VERSION)])
def test_an_item_at_or_above_the_record_version_needs_nothing(version: int | Decimal) -> None:
    assert plan_item_upgrade(end_state_item("inc-1", version=version), TENANTS) is None  # type: ignore[arg-type]


@pytest.mark.parametrize("version", [0, -1, "x", True, Decimal("1.5")])
def test_an_unreadable_record_version_is_reported_by_field_without_its_value(version: object) -> None:
    planned = plan_item_upgrade(end_state_item("inc-1", version=version), TENANTS)  # type: ignore[arg-type]

    assert planned == UnreadableLegacyItem(incident_id="inc-1", field="record_version", value=None)


def test_an_unmatched_legacy_status_is_the_bridges_result_with_its_value() -> None:
    planned = plan_item_upgrade(legacy_item("inc-1", status="Resolved"), TENANTS)

    assert planned == UnreadableLegacyItem(incident_id="inc-1", field="status", value="Resolved")


def test_a_non_integral_decimal_read_value_is_unreadable_and_carries_no_value() -> None:
    planned = plan_item_upgrade(legacy_item("inc-1", severity=Decimal("2.5")), TENANTS)

    assert isinstance(planned, UnreadableLegacyItem)
    assert planned.value is None


def test_a_conversation_id_with_the_key_separator_is_an_unreadable_conversation() -> None:
    planned = plan_item_upgrade(legacy_item("inc-1", channel_id="C0#BAD"), TENANTS)

    assert planned == UnreadableLegacyItem(incident_id="inc-1", field="conversation", value=None)


def test_an_unreadable_stored_conversation_on_a_version_one_item_is_reported() -> None:
    planned = plan_item_upgrade(end_state_item("inc-1", conversation={"system": "slack"}), TENANTS)

    assert planned == UnreadableLegacyItem(incident_id="inc-1", field="conversation", value=None)


@pytest.mark.parametrize(("attribute", "field"), [("declared_by", "declared_by"), ("declared_at", "declared_at")])
def test_a_version_one_item_without_its_declarer_or_time_is_unreadable(attribute: str, field: str) -> None:
    planned = plan_item_upgrade(end_state_item("inc-1", **{attribute: None}), TENANTS)

    assert planned == UnreadableLegacyItem(incident_id="inc-1", field=field, value=None)


def test_a_version_one_item_with_an_unknown_status_is_reported_with_the_status() -> None:
    planned = plan_item_upgrade(end_state_item("inc-1", status="Resolved"), TENANTS)

    assert planned == UnreadableLegacyItem(incident_id="inc-1", field="status", value="Resolved")


def test_the_legacy_changes_name_only_end_state_attributes_and_the_marker() -> None:
    planned = _upgrade(legacy_item("inc-1"))

    legacy_only = {
        "name",
        "user_id",
        "created_at",
        "channel_id",
        "channel_name",
        "report_url",
        "meet_url",
        "teams",
        "environment",
    }
    assert legacy_only.isdisjoint(_set(planned))
