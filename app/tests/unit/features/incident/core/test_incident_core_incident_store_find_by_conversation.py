"""Behavior tests for IncidentStore.find_by_conversation.

The real store runs over InMemoryRecordStore with items shaped as the writers
store them, so the by_channel index read returns full items. Two tenants can
share one channel id, so only candidates whose conversation system and tenant
match the caller's reference count. The zero, one, several and blank-id cases
also run against the in-memory fake, which must classify the same way.
"""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordQuery, RecordStore
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.domain import ConversationReference, Incident
from features.incident.core.store import IncidentStore, RecordIncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = incidents_table("incidents")
CHANNEL = "C0INCIDENT"
TENANT = "T0TENANT"
TENANTS = {WorkplaceSystem.SLACK: TENANT}
OTHER_TENANT = "T0OTHER"
CONVERSATION = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id=CHANNEL)


def _conversation_map(tenant: str = TENANT, channel: str = CHANNEL) -> dict[str, Any]:
    return {"system": "slack", "tenant": tenant, "vendor_id": channel}


def _item(incident_id: str, *, tenant: str = TENANT, channel: str = CHANNEL, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": incident_id,
        "record_version": Decimal(1),
        "title": f"Incident {incident_id}",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
        "product": "GC Notify",
        "channel_id": channel,
        "conversation": _conversation_map(tenant, channel),
    }
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not None}


def _store(*items: dict[str, Any]) -> RecordIncidentStore:
    records = InMemoryRecordStore()
    for item in items:
        assert records.put(TABLE, item).is_success
    return RecordIncidentStore(records, TABLE, TENANTS)


def _incident(incident_id: str, conversation: ConversationReference | None = CONVERSATION) -> Incident:
    return Incident(
        id=incident_id,
        title=f"Incident {incident_id}",
        status=IncidentStatus.OPEN,
        declared_by="U0DECLARER",
        declared_at=datetime(2026, 10, 15, 14, 0, tzinfo=UTC),
        security_incident=False,
        conversation=conversation,
    )


def _real(*incident_ids: str) -> IncidentStore:
    return _store(*(_item(incident_id) for incident_id in incident_ids))


def _fake(*incident_ids: str) -> IncidentStore:
    store = InMemoryIncidentStore()
    for incident_id in incident_ids:
        store.seed(_incident(incident_id))
    return store


def _blank_conversation() -> ConversationReference:
    return MagicMock(spec=ConversationReference, system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id=" ", url=None)


BOTH = pytest.mark.parametrize("build", [_real, _fake], ids=["record_store", "fake"])


@BOTH
def test_no_incident_in_the_conversation_is_not_an_incident(build: Callable[..., IncidentStore]) -> None:
    result = build().find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


@BOTH
def test_one_incident_in_the_conversation_is_found(build: Callable[..., IncidentStore]) -> None:
    result = build("inc-1").find_by_conversation(CONVERSATION)

    assert result.is_success
    assert result.data is not None
    assert result.data.id == "inc-1"
    assert result.data.conversation == CONVERSATION


@BOTH
def test_several_incidents_in_the_conversation_are_ambiguous(build: Callable[..., IncidentStore]) -> None:
    result = build("inc-1", "inc-2").find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION


@BOTH
def test_a_blank_conversation_id_is_not_an_incident(build: Callable[..., IncidentStore]) -> None:
    """A reference cannot be built with a blank id, so a stand-in carries one past that check."""
    result = build("inc-1").find_by_conversation(_blank_conversation())

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


def test_the_index_read_returns_non_key_attributes() -> None:
    """The by_channel index projects every attribute, so the found incident is complete without a second get."""
    result = _real("inc-1").find_by_conversation(CONVERSATION)

    assert result.data is not None
    assert result.data.product == "GC Notify"


def test_a_blank_conversation_id_queries_nothing() -> None:
    records = MagicMock(spec=RecordStore)
    RecordIncidentStore(records, TABLE, TENANTS).find_by_conversation(_blank_conversation())

    records.query.assert_not_called()


def test_two_tenants_sharing_one_channel_id_are_told_apart() -> None:
    """The other tenant's incident shares the index partition but is skipped."""
    store = _store(_item("inc-ours"), _item("inc-theirs", tenant=OTHER_TENANT))

    result = store.find_by_conversation(CONVERSATION)

    assert result.data is not None
    assert result.data.id == "inc-ours"
    theirs = store.find_by_conversation(
        ConversationReference(system=WorkplaceSystem.SLACK, tenant=OTHER_TENANT, vendor_id=CHANNEL)
    )
    assert theirs.data is not None
    assert theirs.data.id == "inc-theirs"


def test_two_incidents_of_the_same_tenant_in_one_channel_are_ambiguous_beside_another_tenant() -> None:
    store = _store(_item("inc-1"), _item("inc-2"), _item("inc-theirs", tenant=OTHER_TENANT))

    assert store.find_by_conversation(CONVERSATION).error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION


def test_an_unreadable_candidate_of_another_tenant_does_not_fail_the_call() -> None:
    """Candidates are filtered by tenant before parsing, so another tenant's broken item is never read."""
    store = _store(_item("inc-ours"), _item("inc-theirs", tenant=OTHER_TENANT, status="bogus"))

    result = store.find_by_conversation(CONVERSATION)

    assert result.data is not None
    assert result.data.id == "inc-ours"


def test_a_candidate_with_an_unreadable_conversation_map_is_skipped() -> None:
    store = _store(_item("inc-ours"), _item("inc-broken", conversation={"system": "teams"}))

    assert store.find_by_conversation(CONVERSATION).data is not None


def test_an_unreadable_candidate_fails_closed_as_unreadable() -> None:
    """The candidate has no record_version and no legacy name, so its tenant cannot be checked and the lookup refuses instead of guessing."""
    store = _store(_item("inc-ours"), _item("inc-legacy", record_version=None))

    result = store.find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE


def test_reaching_the_query_bound_is_ambiguous_without_a_fallback() -> None:
    """A full page means more may exist, so the lookup fails closed and reads no further."""
    records = InMemoryRecordStore()
    for number in range(10):
        records.put(TABLE, _item(f"inc-{number}", tenant=OTHER_TENANT))
    spy = MagicMock(wraps=records)
    store = RecordIncidentStore(spy, TABLE, TENANTS)

    result = store.find_by_conversation(CONVERSATION)

    assert result.error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION
    assert spy.query.call_args_list == [((TABLE, RecordQuery(partition=CHANNEL, index="by_channel", limit=10)),)]


def test_a_store_failure_is_classified_with_its_retry_hint() -> None:
    records = MagicMock(spec=RecordStore)
    records.query.return_value = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR, message="ThrottlingException", error_code="THROTTLED", retry_after=1.5
    )

    result = RecordIncidentStore(records, TABLE, TENANTS).find_by_conversation(CONVERSATION)

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "THROTTLED", 1.5)
    assert result.message is not None
    assert "Throttling" not in result.message
