"""Behavior tests for how the status-update entry points resolve the incident of a channel.

The command handler runs over a fake service scope opener that resolves an
InMemoryRecordStore holding incident items as stored, and Slack configured under
one tenant, so the real store builder, the legacy item bridge and the by_channel
read all take part. One pending draft is seeded in the same record store
through the status-update store builder, so the handler's own store finds it.
Each test asserts the view text the
responder sees, and that the one scope the handler opened was closed.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from contracts.operations import OperationResult
from contracts.records import RecordQuery, RecordTable
from contracts.slack.models import CommandPayload
from features.incident.comms.entrypoints.slack import handle_status_update_command
from features.incident.core.api import StatusUpdate, StatusUpdateStage, StatusUpdateState, StatusUpdateText
from features.incident.core.store import incidents_table
from infrastructure.records.in_memory import InMemoryRecordStore
from tests.factories.incident import SLACK_TENANT, incident_scopes, status_update_store_in
from tests.factories.services import FakeServiceScopeOpener
from tests.factories.slack import FakeSlackReply

pytestmark = pytest.mark.unit

_CHANNEL = "C0INCIDENT"
_INCIDENT = "inc-uuid-1"
_TABLE = incidents_table("incidents")
_NOW = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)


def _legacy_item(incident_id: str = _INCIDENT, **overrides: Any) -> dict[str, Any]:
    """An item as the legacy writers stored it: no record_version, lowercase status, epoch created_at."""
    item: dict[str, Any] = {
        "id": incident_id,
        "channel_id": _CHANNEL,
        "name": f"Incident {incident_id}",
        "user_id": "U0DECLARER",
        "teams": ["GC Notify"],
        "status": "closed",
        "created_at": "1760536800.0",
    }
    item.update(overrides)
    return item


def _end_state_item(incident_id: str, *, tenant: str) -> dict[str, Any]:
    return {
        "id": incident_id,
        "record_version": Decimal(1),
        "title": f"Incident {incident_id}",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
        "channel_id": _CHANNEL,
        "conversation": {"system": "slack", "tenant": tenant, "vendor_id": _CHANNEL},
    }


def _seeded[R: InMemoryRecordStore](records: R, *items: dict[str, Any]) -> R:
    """Put the incident ``items`` and one pending draft for the incident into ``records``."""
    for item in items:
        assert records.put(_TABLE, item).is_success
    assert status_update_store_in(records).append(_pending()).is_success
    return records


def _records(*items: dict[str, Any]) -> InMemoryRecordStore:
    return _seeded(InMemoryRecordStore(), *items)


class _FailingQueries(InMemoryRecordStore):
    """Every query fails as a throttled store would."""

    def query(self, table: RecordTable, spec: RecordQuery) -> OperationResult:
        return OperationResult.transient_error(message="throttled", error_code="THROTTLED")


def _pending(incident_id: str = _INCIDENT) -> StatusUpdate:
    text = StatusUpdateText(affected_service="Notify", impact="Slow", current_action="Investigating", workaround="None")
    return StatusUpdate(
        incident_id=incident_id,
        sequence=1,
        state=StatusUpdateState.DRAFT,
        stage=StatusUpdateStage.IDENTIFIED,
        en=text,
        fr=text,
        next_update_at=_NOW,
        author="U0",
        transcript_cutoff=_NOW,
        transcript_fingerprint="v1:sha256:abc",
        created_at=_NOW,
    )


def _run(scopes: FakeServiceScopeOpener) -> str:
    """Run the command in the incident channel; return the text of the view it ends on."""
    payload = CommandPayload(text="", user_id="U9", channel_id=_CHANNEL, platform_metadata={"trigger_id": "trigger-1"})
    reply = FakeSlackReply(OperationResult.success(data="view-1"))

    handle_status_update_command(payload, {}, reply, scopes)

    view = reply.calls_to("update_view")[-1]["view"]
    return "\n".join(block["text"]["text"] for block in view["blocks"] if block["type"] == "section")


def test_a_legacy_item_resolves_and_its_pending_draft_shows() -> None:
    """An item stored before the record format is upgraded by the bridge and found through the by_channel read."""
    scopes = incident_scopes(_records(_legacy_item()))

    text = _run(scopes)

    assert "Affected service: Notify" in text
    assert (scopes.opened, scopes.closed) == (1, 1)


def test_an_end_state_item_of_the_configured_tenant_resolves() -> None:
    """The conversation reference carries the configured Slack tenant, which the stored reference matches."""
    scopes = incident_scopes(_records(_end_state_item(_INCIDENT, tenant=SLACK_TENANT)))

    assert "Affected service: Notify" in _run(scopes)


def test_an_item_of_another_tenant_on_the_same_channel_is_not_an_incident() -> None:
    """Two tenants can share a channel id; only the configured Slack tenant's incident counts."""
    scopes = incident_scopes(_records(_end_state_item(_INCIDENT, tenant="T0OTHER")))

    assert "not an incident channel" in _run(scopes)


def test_a_channel_without_an_incident_is_refused() -> None:
    scopes = incident_scopes(_records(_legacy_item(channel_id="C0ELSEWHERE")))

    assert "not an incident channel" in _run(scopes)


def test_a_channel_with_two_incidents_is_ambiguous() -> None:
    scopes = incident_scopes(_records(_legacy_item("inc-a"), _legacy_item("inc-b")))

    assert "More than one incident uses this channel" in _run(scopes)


def test_a_store_failure_shows_the_generic_error_and_closes_the_scope() -> None:
    scopes = incident_scopes(_seeded(_FailingQueries()))

    text = _run(scopes)

    assert "Couldn't load the status update right now" in text
    assert (scopes.opened, scopes.closed) == (1, 1)
