"""Behavior tests for IncidentStore reads of legacy items through the bridge.

RecordIncidentStore runs over InMemoryRecordStore with legacy items shaped as
the legacy writers stored them next to end-state items. An item without
record_version is upgraded on read with the configured tenants; an item with
it is parsed as stored. A legacy item the bridge cannot read is
INCIDENT_RECORD_UNREADABLE, logged with the incident id and the legacy
attribute.
"""

from decimal import Decimal
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.domain import ConversationReference
from features.incident.core.store import OPEN_BUCKET, RecordIncidentStore, incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore

pytestmark = pytest.mark.unit

TABLE = incidents_table("incidents")
SLACK_TENANT = "T0SLACK"
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: "C0GOOGLE"}
CHANNEL = "C0INCIDENT"
CONVERSATION = ConversationReference(system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id=CHANNEL)


def _legacy(incident_id: str, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": incident_id,
        "channel_id": CHANNEL,
        "name": f"Incident {incident_id}",
        "user_id": "U0DECLARER",
        "teams": ["GC Notify"],
        "status": "closed",
        "created_at": "1760536800.0",
        "severity": "sev-2",
        "meet_url": "TBC",
    }
    item.update(overrides)
    return item


def _end_state(incident_id: str, **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": incident_id,
        "record_version": Decimal(1),
        "title": f"Incident {incident_id}",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
        "channel_id": CHANNEL,
        "conversation": {"system": "slack", "tenant": SLACK_TENANT, "vendor_id": CHANNEL},
    }
    item.update(overrides)
    return item


def _store(*items: dict[str, Any], tenants: dict[WorkplaceSystem, str] | None = None) -> RecordIncidentStore:
    records = InMemoryRecordStore()
    for item in items:
        assert records.put(TABLE, item).is_success
    return RecordIncidentStore(records, TABLE, TENANTS if tenants is None else tenants)


def test_a_legacy_item_reads_as_the_incident() -> None:
    result = _store(_legacy("inc-legacy")).get("inc-legacy")

    assert result.data is not None
    assert (result.data.title, result.data.status, result.data.severity) == (
        "Incident inc-legacy",
        IncidentStatus.CLOSED,
        Severity.SEV2,
    )
    assert result.data.conversation == CONVERSATION


def test_an_item_with_record_version_bypasses_the_bridge() -> None:
    """An end-state item carrying a legacy-looking status stays unreadable: only the bridge folds case."""
    result = _store(_end_state("inc-new", status="closed")).get("inc-new")

    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE


def test_an_unreadable_legacy_item_is_classified_and_logged_with_its_field() -> None:
    with capture_logs() as logs:
        result = _store(_legacy("inc-legacy", status="Done")).get("inc-legacy")

    assert result.status is OperationStatus.PERMANENT_ERROR
    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE
    unreadable = [log for log in logs if log["event"] == "incident_record_unreadable"]
    assert [(log["operation"], log["incident_id"], log["field"], log["value"]) for log in unreadable] == [
        ("get", "inc-legacy", "status", "Done")
    ]


def test_a_legacy_item_without_a_configured_slack_tenant_is_unreadable() -> None:
    with capture_logs() as logs:
        result = _store(_legacy("inc-legacy"), tenants={}).get("inc-legacy")

    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE
    assert [log["field"] for log in logs if log["event"] == "incident_record_unreadable"] == ["channel_id"]


def test_the_security_flag_of_a_legacy_item_without_one_is_false() -> None:
    result = _store(_legacy("inc-legacy")).read_security_flag("inc-legacy")

    assert result.is_success
    assert result.data is False


def test_a_legacy_incident_is_found_by_its_conversation() -> None:
    result = _store(_legacy("inc-legacy")).find_by_conversation(CONVERSATION)

    assert result.data is not None
    assert result.data.id == "inc-legacy"


def test_a_legacy_and_an_end_state_incident_on_one_conversation_are_ambiguous() -> None:
    result = _store(_legacy("inc-legacy"), _end_state("inc-new")).find_by_conversation(CONVERSATION)

    assert result.error_code == ErrorCode.AMBIGUOUS_INCIDENT_CONVERSATION


def test_a_legacy_candidate_of_another_tenant_is_skipped() -> None:
    """The legacy conversation takes the configured tenant, so a lookup for another tenant does not match it."""
    other = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0OTHER", vendor_id=CHANNEL)
    other_map = {"system": "slack", "tenant": "T0OTHER", "vendor_id": CHANNEL}

    result = _store(_legacy("inc-legacy"), _end_state("inc-other", conversation=other_map)).find_by_conversation(other)

    assert result.data is not None
    assert result.data.id == "inc-other"


def test_an_unreadable_legacy_candidate_fails_the_lookup_closed() -> None:
    result = _store(_end_state("inc-new"), _legacy("inc-legacy", created_at="Unknown")).find_by_conversation(CONVERSATION)

    assert result.error_code == ErrorCode.INCIDENT_RECORD_UNREADABLE


def test_a_legacy_item_in_the_open_index_is_listed() -> None:
    """Only the upgrade job sets open_bucket on legacy items; once set, the list reads them through the bridge."""
    store = _store(
        _legacy("inc-legacy", status="Open", open_bucket=OPEN_BUCKET, opened_at="2025-10-15T14:00:00.000000+00:00"),
        _end_state("inc-new", open_bucket=OPEN_BUCKET, opened_at="2026-10-15T14:00:00.000000+00:00"),
    )

    result = store.list_open()

    assert result.data is not None
    assert [incident.id for incident in result.data] == ["inc-legacy", "inc-new"]
