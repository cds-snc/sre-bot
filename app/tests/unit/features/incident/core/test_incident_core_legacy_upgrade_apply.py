"""Behavior tests for the incident legacy upgrade in apply mode.

Legacy items are seeded in an in-memory record store, upgraded, then read back
both raw (to see the stored attributes) and through RecordIncidentStore (to see
the incident every reader gets). The written record attributes must equal the
shared bridge's output, so the read path and the job hold one mapping.
"""

from decimal import Decimal
from typing import Any

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.adapters.legacy_items import UpgradedItem, upgrade_legacy_item
from features.incident.core.store import OPEN_BUCKET, RECORD_VERSION, RecordIncidentStore
from tests.factories.legacy_upgrade import TABLE, TENANTS, legacy_item, legacy_upgrade, records_with

pytestmark = pytest.mark.unit

LEGACY_ONLY = ("name", "user_id", "created_at", "channel_id", "channel_name", "report_url", "meet_url", "teams", "environment")


def _stored(records: Any, incident_id: str) -> dict[str, Any]:
    result = records.get(TABLE, {"id": incident_id})
    assert result.data is not None
    return dict(result.data)


@pytest.mark.parametrize(
    "item",
    [
        legacy_item("inc-full"),
        legacy_item(
            "inc-minimal",
            channel_id=None,
            report_url=None,
            meet_url=None,
            severity=None,
            teams=None,
            detection_time=None,
            start_impact_time=None,
            incident_commander=None,
            operations_lead=None,
            security_incident=None,
        ),
        legacy_item("inc-dropped", severity="critical", meet_url="TBC", report_url="https://example.com/report"),
    ],
    ids=["every-field", "minimal", "with-drops"],
)
def test_apply_writes_the_bridge_output_and_the_version_marker(item: dict[str, Any]) -> None:
    upgraded = upgrade_legacy_item(item, TENANTS)
    assert isinstance(upgraded, UpgradedItem)
    records = records_with(item)

    report = legacy_upgrade(records).run(apply=True)

    stored = _stored(records, item["id"])
    assert (report.outcome, report.upgraded, report.pending) == ("succeeded", 1, 0)
    assert {key: stored[key] for key in upgraded.item} == upgraded.item
    assert stored["record_version"] == RECORD_VERSION


def test_the_happy_path_closed_incident_reads_the_same_after_the_upgrade() -> None:
    """A single-team Closed incident with every field mappable: no open index, product unset, teams kept."""
    item = legacy_item("inc-closed", status="Closed")
    records = records_with(item)
    before = RecordIncidentStore(records, TABLE, TENANTS).get("inc-closed").data

    legacy_upgrade(records).run(apply=True)

    stored = _stored(records, "inc-closed")
    after = RecordIncidentStore(records, TABLE, TENANTS).get("inc-closed").data
    assert after is not None and after == before
    assert (after.status, after.severity, after.product) == (IncidentStatus.CLOSED, Severity.SEV2, None)
    assert after.conversation is not None and after.conversation.tenant == TENANTS[WorkplaceSystem.SLACK]
    assert {"open_bucket", "opened_at", "product"}.isdisjoint(stored)
    assert stored["teams"] == ["GC Notify"]


def test_the_open_security_incident_most_likely_to_break_upgrades_whole() -> None:
    """Several teams, lowercase status, no stored flag and a numeric created_at: open index set, flag false, product unset."""
    item = legacy_item(
        "inc-open",
        status=" in progress ",
        teams=["GC Notify", "GC Forms"],
        security_incident=None,
        created_at=Decimal(1760536800),
    )
    records = records_with(item)

    report = legacy_upgrade(records).run(apply=True)

    stored = _stored(records, "inc-open")
    assert report.upgraded == 1
    assert (stored["status"], stored["security_incident"]) == ("In Progress", False)
    assert stored["open_bucket"] == OPEN_BUCKET
    assert stored["opened_at"] == stored["declared_at"] == "2025-10-15T14:00:00.000000+00:00"
    assert "product" not in stored
    assert stored["teams"] == ["GC Notify", "GC Forms"]
    listed = RecordIncidentStore(records, TABLE, TENANTS).list_open().data
    assert [incident.id for incident in listed or []] == ["inc-open"]


@pytest.mark.parametrize(
    ("status", "open_index"),
    [
        ("Open", True),
        ("In Progress", True),
        ("Ready to be Reviewed", True),
        ("reviewed", True),
        ("Closed", False),
        ("closed", False),
    ],
)
def test_only_incidents_not_closed_get_the_open_index(status: str, open_index: bool) -> None:
    records = records_with(legacy_item("inc-1", status=status))

    legacy_upgrade(records).run(apply=True)

    stored = _stored(records, "inc-1")
    assert ("open_bucket" in stored, "opened_at" in stored) == (open_index, open_index)


def test_legacy_attributes_stay_on_the_upgraded_item() -> None:
    item = legacy_item("inc-1")
    records = records_with(item)

    legacy_upgrade(records).run(apply=True)

    stored = _stored(records, "inc-1")
    assert {key: stored[key] for key in LEGACY_ONLY} == {key: item[key] for key in LEGACY_ONLY}
