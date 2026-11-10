"""Legacy incident items and a configured incident legacy upgrade for tests of the upgrade runner.

Items are put into an in-memory record store as the legacy writers stored them;
the upgrade reads them back with a whole-table read, so a test observes the same
read, guard and write path the scheduled job takes.
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from contracts.operations import OperationResult
from contracts.records import ExpectedValue, RecordChange, RecordTable
from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.incident_items import END_STATE_VERSION, OPEN_BUCKET
from features.incident.core.adapters.legacy_items import UpgradedItem, upgrade_legacy_item
from features.incident.core.legacy_upgrade import LegacyUpgrade
from features.incident.core.store import bindings_table, incidents_table
from tests.factories.incident import SLACK_TENANT, CountingRecordStore
from tests.factories.tenant_verifier import FakeTenantVerifier

TABLE = incidents_table("incidents")
BINDINGS = bindings_table("bindings")
GOOGLE_TENANT = "C0GOOGLE"
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
REPORT_URL = "https://docs.google.com/document/d/doc123/edit"
MEET_URL = "https://meet.google.com/abc-defg-hij"


def legacy_item(incident_id: str = "inc-legacy", **overrides: Any) -> dict[str, Any]:
    """A legacy incident item with every mappable attribute; an override of ``None`` removes the attribute."""
    item: dict[str, Any] = {
        "id": incident_id,
        "name": f"Incident {incident_id}",
        "user_id": "U0DECLARER",
        "status": "Open",
        "created_at": "1760536800.0",
        "channel_id": f"C0{incident_id.upper()}",
        "channel_name": f"incident-{incident_id}",
        "teams": ["GC Notify"],
        "report_url": REPORT_URL,
        "meet_url": MEET_URL,
        "severity": "sev-2",
        "detection_time": "1760536700",
        "start_impact_time": "1760536600",
        "end_impact_time": "Unknown",
        "incident_commander": "U0COMMANDER",
        "operations_lead": "U0OPS",
        "security_incident": False,
        "environment": "prod",
    }
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not None}


def end_state_item(incident_id: str = "inc-v1", version: int = END_STATE_VERSION, **overrides: Any) -> dict[str, Any]:
    """An end-state incident item at ``version`` without a binding, as the bridge maps ``legacy_item(incident_id)``.

    An override of ``None`` removes the attribute. Open items carry the open index; a ``Closed`` one does not.
    """
    upgraded = upgrade_legacy_item(legacy_item(incident_id), TENANTS)
    assert isinstance(upgraded, UpgradedItem)
    item: dict[str, Any] = {**upgraded.item, "record_version": version, "channel_id": f"C0{incident_id.upper()}"}
    item.update(overrides)
    if item["status"] != "Closed":
        item.setdefault("open_bucket", OPEN_BUCKET)
        item.setdefault("opened_at", item["declared_at"])
    return {key: value for key, value in item.items() if value is not None}


def verified_slack(tenant: str = SLACK_TENANT) -> FakeTenantVerifier:
    """A tenant verifier confirming ``tenant`` for Slack."""
    return FakeTenantVerifier({WorkplaceSystem.SLACK: OperationResult.success(data=tenant)})


class InterceptingRecordStore(CountingRecordStore):
    """Counting in-memory store that runs ``before_update`` (with the key) before each update, to act as a concurrent writer."""

    def __init__(self) -> None:
        super().__init__()
        self.before_update: Callable[[dict[str, Any]], None] | None = None

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        if self.before_update is not None:
            self.before_update(key)
        return super().update(table, key, changes, expected=expected)


def records_with(*items: dict[str, Any]) -> InterceptingRecordStore:
    """A store holding ``items`` in the incidents table; seeding is not counted as a write."""
    records = InterceptingRecordStore()
    for item in items:
        assert records.put(TABLE, item).is_success
    records.writes.clear()
    return records


def legacy_upgrade(
    records: InterceptingRecordStore,
    *,
    verifier: FakeTenantVerifier | None = None,
    tenants: Mapping[WorkplaceSystem, str] = TENANTS,
    max_items: int = 100,
) -> LegacyUpgrade:
    """The upgrade over ``records`` with the configured tenants and, by default, a verifier confirming the Slack tenant."""
    return LegacyUpgrade(
        records, TABLE, tenants, verified_slack() if verifier is None else verifier, max_items, bindings=BINDINGS
    )
