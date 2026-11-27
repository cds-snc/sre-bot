"""Unit tests for reading webhook instances from the webhooks table.

Items are seeded into ``InMemoryRecordStore`` in the stored shape the backfill writes (the
legacy attributes plus the new optional ones). Assertions check what the store returns: a
provisioned instance, or NOT_FOUND for a legacy-only, disabled-by-flag-only or unreadable item.
"""

from typing import Any

import pytest

from capabilities.webhooks.domain.kinds import AuthTier, Destination, InstanceState
from capabilities.webhooks.store import RecordWebhookStore, instances_table
from contracts.operations import OperationStatus
from contracts.workplace import WorkplaceSystem
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = instances_table("webhooks")


def _provisioned(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": "url-token-1",
        "name": "budgets",
        "channel": "C-LEGACY",
        "active": True,
        "hook_type": "alert",
        "instance_ref": "ref-1",
        "protocol": "aws_sns",
        "sender_kinds": ["budget-alert"],
        "destinations": [{"system": "slack", "tenant": "T1", "conversation_id": "C1", "triage": True}],
        "owner": {"team": "sre", "contact": "sre@example.com"},
        "auth_tier": "legacy",
        "topic_arns": ["arn:aws:sns:ca-central-1:123456789012:budgets"],
    }
    item.update(overrides)
    return {name: value for name, value in item.items() if value is not None}


def _store(*items: dict[str, Any]) -> RecordWebhookStore:
    records = InMemoryRecordStore()
    for item in items:
        records.put(TABLE, item)
    return RecordWebhookStore(records, TABLE)


async def test_a_provisioned_item_reads_as_its_instance_by_url_token_and_by_ref() -> None:
    store = _store(_provisioned())

    by_url = await store.by_url_id("url-token-1")
    by_ref = await store.by_ref("ref-1")

    assert by_url.data == by_ref.data
    instance = by_url.data
    assert instance is not None
    assert (instance.instance_ref, instance.protocol, instance.auth_tier, instance.state) == (
        "ref-1",
        "aws_sns",
        AuthTier.LEGACY,
        InstanceState.ACTIVE,
    )
    assert instance.destinations == (Destination(WorkplaceSystem.SLACK, "T1", "C1", triage=True),)
    assert instance.topic_arns == ("arn:aws:sns:ca-central-1:123456789012:budgets",)


@pytest.mark.parametrize(
    "item",
    [
        pytest.param(_provisioned(instance_ref=None, protocol=None), id="legacy-only"),
        pytest.param(_provisioned(owner=None), id="no-owner"),
        pytest.param(_provisioned(auth_tier="unknown"), id="unknown-tier"),
    ],
)
async def test_an_item_that_is_not_a_readable_provisioned_instance_is_not_found(item: dict[str, Any]) -> None:
    result = await _store(item).by_url_id("url-token-1")

    assert result.status is OperationStatus.NOT_FOUND


async def test_the_legacy_active_flag_decides_the_state_until_a_state_is_stored() -> None:
    legacy_off = await _store(_provisioned(active=False)).by_url_id("url-token-1")
    stored_state = await _store(_provisioned(active=False, state="active")).by_url_id("url-token-1")

    assert legacy_off.data is not None and legacy_off.data.state is InstanceState.DISABLED
    assert stored_state.data is not None and stored_state.data.state is InstanceState.ACTIVE


async def test_an_unreadable_destination_is_dropped_and_the_rest_kept() -> None:
    destinations = [
        {"system": "teams-of-unknown", "tenant": "T", "conversation_id": "C"},
        {"system": "slack", "tenant": "T1", "conversation_id": "C2"},
    ]

    result = await _store(_provisioned(destinations=destinations)).by_url_id("url-token-1")

    assert result.data is not None
    assert [destination.conversation_id for destination in result.data.destinations] == ["C2"]


async def test_the_url_token_never_appears_on_the_instance() -> None:
    result = await _store(_provisioned()).by_url_id("url-token-1")

    assert "url-token-1" not in repr(result.data)
