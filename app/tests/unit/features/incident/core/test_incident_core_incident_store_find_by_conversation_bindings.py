"""Behavior tests for IncidentStore.find_by_conversation reading bindings first.

The lookup reads the bindings table (index by_conversation) and falls back to the
incidents table (index by_channel) only when no active binding names a record
that exists; the two sources are never merged. The cases that need no store
failure injection run against the real store over InMemoryRecordStore and the
in-memory fake, which must classify them the same way. Failure injection and
raw-item cases run on the real store only.
"""

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import RecordQuery, RecordStore
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.binding_items import binding_item
from features.incident.core.adapters.in_memory import InMemoryIncidentStore
from features.incident.core.domain import IncidentBinding
from features.incident.core.store import IncidentStore, RecordIncidentStore, bindings_table, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import (
    DECLARED_AT,
    SLACK_TENANT,
    binding_on,
    incident_on,
    record_incident_store,
    slack_conversation,
)

pytestmark = pytest.mark.unit

INCIDENTS = incidents_table("incidents")
BINDINGS = bindings_table("bindings")
CHANNEL = "C0INCIDENT"
ELSEWHERE = "C0ELSEWHERE"
OTHER_TENANT = "T0OTHER"
CONVERSATION = slack_conversation(CHANNEL)

# incident id -> channel its own record names
type Incidents = Mapping[str, str]


def _item(incident_id: str, channel: str, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": incident_id,
        "record_version": Decimal(1),
        "title": f"Incident {incident_id}",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
        "channel_id": channel,
        "conversation": {"system": "slack", "tenant": SLACK_TENANT, "vendor_id": channel},
    }
    item.update(overrides)
    return item


def _real_records(incidents: Incidents, bindings: Sequence[IncidentBinding]) -> InMemoryRecordStore:
    records = InMemoryRecordStore()
    for incident_id, channel in incidents.items():
        assert records.put(INCIDENTS, _item(incident_id, channel)).is_success
    for binding in bindings:
        assert records.put(BINDINGS, binding_item(binding)).is_success
    return records


def _real(incidents: Incidents, bindings: Sequence[IncidentBinding] = ()) -> IncidentStore:
    return record_incident_store(_real_records(incidents, bindings), table=INCIDENTS, bindings=BINDINGS)


def _fake(incidents: Incidents, bindings: Sequence[IncidentBinding] = ()) -> IncidentStore:
    store = InMemoryIncidentStore()
    for incident_id, channel in incidents.items():
        store.seed(incident_on(channel, incident_id))
    for binding in bindings:
        store.bind(binding)
    return store


BOTH = pytest.mark.parametrize("build", [_real, _fake], ids=["record_store", "fake"])
Build = Callable[..., IncidentStore]


@BOTH
def test_an_active_binding_finds_its_incident_even_when_the_record_names_another_channel(build: Build) -> None:
    """The binding decides: the incident's own record is on a different channel, so by_channel alone could not find it."""
    result = build({"inc-1": ELSEWHERE}, [binding_on(CHANNEL, "inc-1")]).find_by_conversation(CONVERSATION)

    assert result.is_success
    assert result.data is not None and result.data.id == "inc-1"


@BOTH
def test_without_a_binding_the_by_channel_lookup_answers(build: Build) -> None:
    result = build({"inc-1": CHANNEL}).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.id == "inc-1"


@BOTH
def test_a_binding_does_not_merge_with_by_channel_candidates(build: Build) -> None:
    """One bound incident and a different incident on the channel: only the bound one answers, with no ambiguity."""
    result = build({"inc-bound": ELSEWHERE, "inc-channel": CHANNEL}, [binding_on(CHANNEL, "inc-bound")]).find_by_conversation(
        CONVERSATION
    )

    assert result.data is not None and result.data.id == "inc-bound"


@BOTH
def test_a_binding_whose_record_is_missing_is_not_an_incident(build: Build) -> None:
    result = build({}, [binding_on(CHANNEL, "inc-ghost")]).find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.NOT_FOUND
    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


@BOTH
def test_a_dangling_binding_falls_through_to_by_channel(build: Build) -> None:
    result = build({"inc-channel": CHANNEL}, [binding_on(CHANNEL, "inc-ghost")]).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.id == "inc-channel"


@BOTH
def test_a_dangling_binding_beside_a_live_one_resolves_to_the_live_incident(build: Build) -> None:
    """A crashed declare then a retry with a new incident id: the dangling binding does not make the channel ambiguous."""
    result = build(
        {"inc-retry": ELSEWHERE}, [binding_on(CHANNEL, "inc-crashed"), binding_on(CHANNEL, "inc-retry")]
    ).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.id == "inc-retry"


@BOTH
def test_two_active_bindings_whose_records_exist_are_ambiguous_with_no_fallback(build: Build) -> None:
    result = build(
        {"inc-1": ELSEWHERE, "inc-2": ELSEWHERE, "inc-channel": CHANNEL},
        [binding_on(CHANNEL, "inc-1"), binding_on(CHANNEL, "inc-2")],
    ).find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION


@BOTH
def test_an_archived_binding_is_ignored(build: Build) -> None:
    archived = binding_on(CHANNEL, "inc-1", archived_at=DECLARED_AT)

    result = build({"inc-1": ELSEWHERE}, [archived]).find_by_conversation(CONVERSATION)

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


@BOTH
def test_an_archived_binding_beside_the_active_one_leaves_one_candidate(build: Build) -> None:
    bindings = [binding_on(CHANNEL, "inc-old", archived_at=DECLARED_AT, primary=False), binding_on(CHANNEL, "inc-new")]

    result = build({"inc-old": ELSEWHERE, "inc-new": ELSEWHERE}, bindings).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.id == "inc-new"


@BOTH
def test_a_binding_of_another_tenant_is_dropped_and_does_not_make_ours_ambiguous(build: Build) -> None:
    bindings = [binding_on(CHANNEL, "inc-theirs", tenant=OTHER_TENANT), binding_on(CHANNEL, "inc-ours")]

    result = build({"inc-theirs": ELSEWHERE, "inc-ours": ELSEWHERE}, bindings).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.id == "inc-ours"


@BOTH
def test_only_a_binding_of_another_tenant_is_not_an_incident(build: Build) -> None:
    result = build({"inc-theirs": ELSEWHERE}, [binding_on(CHANNEL, "inc-theirs", tenant=OTHER_TENANT)]).find_by_conversation(
        CONVERSATION
    )

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


@BOTH
def test_a_binding_of_another_conversation_is_not_considered(build: Build) -> None:
    result = build({"inc-1": ELSEWHERE}, [binding_on(ELSEWHERE, "inc-1")]).find_by_conversation(CONVERSATION)

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


@BOTH
def test_a_blank_conversation_id_is_not_an_incident(build: Build) -> None:
    blank = MagicMock(spec=type(CONVERSATION), system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id=" ", url=None)

    result = build({"inc-1": CHANNEL}, [binding_on(CHANNEL, "inc-1")]).find_by_conversation(blank)

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


def test_a_blank_conversation_id_issues_no_query() -> None:
    spy = MagicMock(wraps=_real_records({}, []))
    blank = MagicMock(spec=type(CONVERSATION), system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id=" ", url=None)

    record_incident_store(spy, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(blank)

    spy.query.assert_not_called()


def test_a_closed_incident_still_resolves_through_its_binding() -> None:
    records = _real_records({}, [binding_on(CHANNEL, "inc-1")])
    assert records.put(INCIDENTS, _item("inc-1", ELSEWHERE, status="Closed")).is_success

    result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.status is IncidentStatus.CLOSED


def test_a_legacy_item_behind_a_binding_resolves_through_the_legacy_bridge() -> None:
    """The upgrade job puts the binding before it raises the item to the end-state shape."""
    records = _real_records({}, [binding_on(CHANNEL, "inc-legacy")])
    legacy = {
        "id": "inc-legacy",
        "channel_id": ELSEWHERE,
        "name": "Incident inc-legacy",
        "user_id": "U0DECLARER",
        "teams": ["Platform"],
        "status": "Open",
        "created_at": "1760536800.0",
    }
    assert records.put(INCIDENTS, legacy).is_success

    result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.id == "inc-legacy"


def test_a_binding_without_a_conversation_id_is_never_reached() -> None:
    """A binding of a non-chat place has no conversation_id, so it is absent from the sparse index."""
    records = _real_records({"inc-1": ELSEWHERE}, [])
    item = {k: v for k, v in binding_item(binding_on(CHANNEL, "inc-1")).items() if k != "conversation_id"}
    assert records.put(BINDINGS, item).is_success

    result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.error_code == ErrorCode.NOT_AN_INCIDENT


def test_a_full_page_of_bindings_is_ambiguous_without_reading_a_record() -> None:
    bindings = [binding_on(CHANNEL, f"inc-{number}") for number in range(10)]
    spy = MagicMock(wraps=_real_records({}, bindings))

    result = record_incident_store(spy, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION
    assert spy.query.call_args_list == [((BINDINGS, RecordQuery(partition=CHANNEL, index="by_conversation", limit=10)),)]
    spy.get.assert_not_called()


def test_a_dropped_binding_warns_naming_both_tenants_and_never_the_vendor_id() -> None:
    store = _real(
        {"inc-theirs": ELSEWHERE, "inc-ours": ELSEWHERE},
        [binding_on(CHANNEL, "inc-theirs", tenant=OTHER_TENANT), binding_on(CHANNEL, "inc-ours")],
    )

    with capture_logs() as logs:
        store.find_by_conversation(CONVERSATION)

    warnings = [log for log in logs if log["event"] == "incident_conversation_candidate_dropped"]
    assert [
        (w["log_level"], w["incident_id"], w["stored_system"], w["stored_tenant"], w["requested_system"], w["requested_tenant"])
        for w in warnings
    ] == [("warning", "inc-theirs", "slack", OTHER_TENANT, "slack", SLACK_TENANT)]
    assert CHANNEL not in repr(warnings)


def _failing(**methods: OperationResult[Any]) -> MagicMock:
    records = MagicMock(wraps=_real_records({"inc-1": CHANNEL}, [binding_on(CHANNEL, "inc-1")]), spec=RecordStore)
    for name, result in methods.items():
        getattr(records, name).return_value = result
    return records


def test_a_bindings_query_failure_is_classified_and_never_falls_back() -> None:
    records = _failing(
        query=OperationResult.error(
            OperationStatus.TRANSIENT_ERROR, message="ThrottlingException", error_code="THROTTLED", retry_after=1.5
        )
    )

    with capture_logs() as logs:
        result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "THROTTLED", 1.5)
    assert result.message is not None and "Throttling" not in result.message
    assert [call.args[0] for call in records.query.call_args_list] == [BINDINGS]
    failed = [log for log in logs if log["event"] == "incident_store_failed"]
    assert [log["table"] for log in failed] == [BINDINGS.name]


def test_a_missing_bindings_index_is_a_permanent_error_not_a_missing_incident() -> None:
    records = _failing(query=OperationResult.error(OperationStatus.NOT_FOUND, message="no such index", error_code="NO_INDEX"))

    result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.PERMANENT_ERROR


def test_a_failure_reading_the_bound_incident_is_classified() -> None:
    records = _failing(
        get=OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="boom", error_code="THROTTLED", retry_after=2.0)
    )

    result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert (result.status, result.error_code, result.retry_after) == (OperationStatus.TRANSIENT_ERROR, "THROTTLED", 2.0)


def test_an_unreadable_bound_incident_fails_closed() -> None:
    records = _real_records({}, [binding_on(CHANNEL, "inc-1")])
    assert records.put(INCIDENTS, _item("inc-1", CHANNEL, title=None)).is_success

    result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE


def test_a_binding_of_an_unknown_kind_is_skipped_with_a_warning_then_the_fallback_answers() -> None:
    records = _real_records({"inc-channel": CHANNEL}, [])
    unknown = {**binding_item(binding_on(CHANNEL, "inc-future")), "kind": "backstage_page"}
    assert records.put(BINDINGS, unknown).is_success

    with capture_logs() as logs:
        result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.data is not None and result.data.id == "inc-channel"
    skipped = [log for log in logs if log["event"] == "incident_binding_unknown_kind"]
    assert [(log["incident_id"], log["kind"]) for log in skipped] == [("inc-future", "backstage_page")]


def test_a_binding_of_a_known_kind_with_an_unreadable_field_fails_closed() -> None:
    records = _real_records({"inc-channel": CHANNEL}, [])
    damaged = {k: v for k, v in binding_item(binding_on(CHANNEL, "inc-1")).items() if k != "bound_at"}
    assert records.put(BINDINGS, damaged).is_success

    result = record_incident_store(records, table=INCIDENTS, bindings=BINDINGS).find_by_conversation(CONVERSATION)

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE


def test_the_store_constructor_requires_the_bindings_table() -> None:
    with pytest.raises(TypeError):
        RecordIncidentStore(InMemoryRecordStore(), INCIDENTS, {})  # type: ignore[call-arg]


def test_the_store_constructor_requires_the_timeline_store() -> None:
    with pytest.raises(TypeError):
        RecordIncidentStore(InMemoryRecordStore(), INCIDENTS, {}, bindings=BINDINGS)  # type: ignore[call-arg]
