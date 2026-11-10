"""Behavior tests for the warning IncidentStore.find_by_conversation logs for a candidate of another tenant.

Two tenants can share one channel id, so the lookup drops a by_channel
candidate stored under another system or tenant. Each drop is logged as a
warning naming the stored and requested system and tenant, so a wrongly stamped
tenant shows in the logs instead of as a silent "not an incident". The store
runs over InMemoryRecordStore; logs are captured with structlog's capture_logs.
"""

from decimal import Decimal
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.records import RecordTable
from contracts.workplace import WorkplaceSystem
from features.incident.core.domain import ConversationReference
from features.incident.core.store import incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import record_incident_store

pytestmark = pytest.mark.unit

TABLE: RecordTable = incidents_table("incidents")
CHANNEL = "C0INCIDENT"
TENANT = "T0TENANT"
CONVERSATION = ConversationReference(system=WorkplaceSystem.SLACK, tenant=TENANT, vendor_id=CHANNEL)


def _item(incident_id: str, *, system: str = "slack", tenant: str = TENANT) -> dict[str, Any]:
    return {
        "id": incident_id,
        "record_version": Decimal(1),
        "title": f"Incident {incident_id}",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
        "channel_id": CHANNEL,
        "conversation": {"system": system, "tenant": tenant, "vendor_id": CHANNEL},
    }


async def _find(*items: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    records = InMemoryRecordStore()
    for item in items:
        assert records.put(TABLE, item).is_success
    store = record_incident_store(records, table=TABLE, tenants={WorkplaceSystem.SLACK: TENANT})
    with capture_logs() as logs:
        result = await store.find_by_conversation(CONVERSATION)
    return result, [log for log in logs if log["event"] == "incident_conversation_candidate_dropped"]


@pytest.mark.parametrize(("system", "tenant"), [("slack", "T0OTHER"), ("google", TENANT)])
async def test_a_candidate_of_another_tenant_is_dropped_with_a_warning_naming_both(system: str, tenant: str) -> None:
    result, warnings = await _find(_item("inc-ours"), _item("inc-theirs", system=system, tenant=tenant))

    assert result.data is not None and result.data.id == "inc-ours"
    assert [
        (w["log_level"], w["incident_id"], w["stored_system"], w["stored_tenant"], w["requested_system"], w["requested_tenant"])
        for w in warnings
    ] == [("warning", "inc-theirs", system, tenant, "slack", TENANT)]
    assert CHANNEL not in repr(warnings)


async def test_a_matching_candidate_logs_no_warning() -> None:
    result, warnings = await _find(_item("inc-ours"))

    assert result.data is not None
    assert warnings == []
