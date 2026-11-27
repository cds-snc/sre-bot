"""The list-sheet row and record a Slack declare writes: the deliberate changes for the sheet's readers.

Runs the declare submission over an in-memory record store and the core in-memory
list projection (its rows are the Sheets adapter's cells, from the shared row
format) and conversation. Assertions read the row's six cells and the stored
record item: column F is the incident id, the status is ``[incident_response]
initial_status`` (Open by default, In Progress when configured), the product cell
is empty (the record keeps no product), and the item carries no legacy ``logs``
list (the declare cutover's named changes 3, 6, 7 and 8).
"""

from collections.abc import Iterator
from typing import Any

import pytest

from capabilities.oncall.adapters.in_memory import InMemoryOnCallLookup
from contracts.workplace import WorkplaceSystem
from features.incident.common.settings import get_incident_core_settings
from features.incident.common.vocabulary import IncidentStatus
from features.incident.core.adapters.in_memory import (
    InMemoryIncidentConversation,
    InMemoryIncidentListProjection,
    InMemoryIncidentReport,
    InMemoryPlacementScheduleLookup,
    InMemoryVideoCall,
)
from features.incident.core.store import incidents_table
from features.incident.response import providers
from features.incident.response.entrypoints.slack_declare import handle_declare_submission
from features.incident.response.service.declare import incident_id_for
from features.incident.response.settings import get_incident_response_settings
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import GOOGLE_TENANT, SLACK_TENANT, incident_scopes
from tests.factories.slack import FakeSlackReply

pytestmark = pytest.mark.unit

INCIDENT_ID = incident_id_for(f"slack:{SLACK_TENANT}:V0VIEW")


class NullSink:
    async def send(self, event: str, message: Any) -> None:
        return None


@pytest.fixture
def projection(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemoryIncidentListProjection]:
    projection = InMemoryIncidentListProjection()
    conversations = InMemoryIncidentConversation(tenant=SLACK_TENANT)
    reports = InMemoryIncidentReport(next_ids=["D0REPORT"], placements=(("F0FORMS", "Forms"),))
    monkeypatch.setattr(providers, "incident_report", lambda: reports)
    monkeypatch.setattr(providers, "incident_list_projection", lambda: projection)
    monkeypatch.setattr(providers, "incident_conversation", lambda: conversations)
    monkeypatch.setattr(providers, "video_call", InMemoryVideoCall)
    monkeypatch.setattr(providers, "placement_schedule_lookup", InMemoryPlacementScheduleLookup)
    monkeypatch.setattr(providers, "oncall_lookup", lambda: InMemoryOnCallLookup(people={}))
    monkeypatch.setattr(providers, "declare_event_sink", NullSink)
    yield projection


def _declare(records: InMemoryRecordStore) -> None:
    body = {
        "trigger_id": "T0",
        "user": {"id": "U0DECLARER"},
        "view": {
            "id": "V0VIEW",
            "private_metadata": "",
            "blocks": [],
            "state": {
                "values": {
                    "name": {"name": {"value": "db down"}},
                    "product": {"product": {"selected_option": {"text": {"text": "Forms"}, "value": "F0FORMS"}}},
                    "severity": {"severity": {"selected_option": {"value": "none"}}},
                    "security_incident": {"security_incident": {"selected_option": {"value": "no"}}},
                }
            },
        },
    }
    tenants = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
    handle_declare_submission(lambda **_: None, body, FakeSlackReply(), incident_scopes(records, tenants=tenants))


def test_the_row_keys_on_the_incident_id_starts_open_and_names_no_product(projection: InMemoryIncidentListProjection) -> None:
    records = InMemoryRecordStore()

    _declare(records)

    [row] = projection.rows
    assert (row[2], row[3], row[5]) == ("", "Open", INCIDENT_ID)
    item = records.get(incidents_table(get_incident_core_settings().incidents_table), {"id": INCIDENT_ID}).data
    assert item is not None and "logs" not in item


def test_the_row_starts_in_the_configured_initial_status(
    projection: InMemoryIncidentListProjection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_incident_response_settings(), "initial_status", IncidentStatus.IN_PROGRESS)

    _declare(InMemoryRecordStore())

    [row] = projection.rows
    assert row[3] == "In Progress"
