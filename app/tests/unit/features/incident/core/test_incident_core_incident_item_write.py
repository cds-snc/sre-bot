"""Behavior tests for the end-state incident item writer.

Pure function tests: ``incident_item`` turns an ``Incident`` into the item the
store puts, and ``parse_incident_item`` must read it back unchanged. The stored
attribute set is compared whole, so a legacy name or a ``None`` placeholder
cannot slip in. The source alert is a message-shaped map; a stored one that
cannot be read is dropped and logged without the map, which may hold a link.
"""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.adapters.incident_items import (
    OPEN_BUCKET,
    RECORD_VERSION,
    incident_item,
    parse_incident_item,
)
from features.incident.core.domain import (
    ConversationReference,
    ExternalCaseReference,
    Incident,
    MessageReference,
    PostmortemMeetingReference,
    ReportReference,
    VideoCallReference,
)

pytestmark = pytest.mark.unit

INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
AT = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)
EASTERN = timezone(timedelta(hours=-4))
CONVERSATION = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0TENANT", vendor_id="C0INCIDENT")
SOURCE_ALERT = MessageReference(
    system=WorkplaceSystem.SLACK,
    tenant="T0TENANT",
    conversation_id="C0ALERTS",
    message_id="1760536800.000100",
    url="https://slack.test/archives/C0ALERTS/p1760536800000100",
)
LEGACY_NAMES = {"name", "user_id", "teams", "created_at", "report_url", "channel_name", "meet_url"}


def _minimal(**overrides: Any) -> Incident:
    fields: dict[str, Any] = {
        "id": INCIDENT_ID,
        "title": "Notify emails delayed",
        "status": IncidentStatus.OPEN,
        "declared_by": "U0DECLARER",
        "declared_at": AT,
        "security_incident": False,
        "conversation": CONVERSATION,
    }
    fields.update(overrides)
    return Incident(**fields)


def _full() -> Incident:
    return _minimal(
        product="gc-notify",
        severity=Severity.SEV1,
        security_incident=True,
        detected_at=AT - timedelta(minutes=30),
        impact_started_at=datetime(2026, 10, 15, 9, 0, tzinfo=EASTERN),
        impact_ended_at=AT + timedelta(hours=1),
        incident_commander="U0IC",
        operations_lead="U0OL",
        communications_lead="U0CL",
        policy_lead="U0PL",
        postmortem_owner="U0PO",
        report=ReportReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="1DOC", url="https://docs.test/1DOC"),
        video_call=VideoCallReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="abc-defg-hij"),
        postmortem_meeting=PostmortemMeetingReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="EV1"),
        external_case=ExternalCaseReference(system=WorkplaceSystem.GOOGLE, tenant="C0GOOGLE", vendor_id="CASE-1"),
        source_alert=SOURCE_ALERT,
    )


def test_a_minimal_item_holds_only_the_required_end_state_names() -> None:
    """An incident declared with no surface stores no conversation and no channel_id; nothing is stored as None."""
    item = incident_item(_minimal(conversation=None))

    assert set(item) == {
        "id",
        "title",
        "status",
        "declared_by",
        "declared_at",
        "security_incident",
        "record_version",
        "open_bucket",
        "opened_at",
    }
    assert None not in item.values()
    assert item["record_version"] == RECORD_VERSION == 2
    assert item["open_bucket"] == OPEN_BUCKET
    assert item["status"] == "Open"


def test_an_incident_with_a_conversation_also_stores_its_lookup_copy() -> None:
    """The conversation map and the top-level channel_id the by_channel index reads are written together."""
    item = incident_item(_minimal())

    assert item["conversation"] == {"system": "slack", "tenant": "T0TENANT", "vendor_id": "C0INCIDENT"}
    assert item["channel_id"] == "C0INCIDENT"


def test_a_full_item_holds_every_record_name_and_no_legacy_name() -> None:
    """Every field of the record is stored under its own name; no legacy attribute is written."""
    item = incident_item(_full())

    assert set(item) >= {
        "product",
        "severity",
        "detected_at",
        "impact_started_at",
        "impact_ended_at",
        "incident_commander",
        "operations_lead",
        "communications_lead",
        "policy_lead",
        "postmortem_owner",
        "report",
        "video_call",
        "postmortem_meeting",
        "external_case",
        "source_alert",
    }
    assert not set(item) & LEGACY_NAMES


def test_severity_is_stored_as_its_number() -> None:
    """The level is the stored value, so the store can compare it; the enum member is not written."""
    stored = incident_item(_full())["severity"]

    assert stored == 1
    assert type(stored) is int


def test_opened_at_is_the_declared_time_in_the_fixed_width_stored_form() -> None:
    """opened_at sorts the open index, so it is the declared time in UTC with microseconds and the +00:00 offset."""
    item = incident_item(_minimal(declared_at=datetime(2026, 10, 15, 10, 0, tzinfo=EASTERN)))

    assert item["opened_at"] == "2026-10-15T14:00:00.000000+00:00"
    assert len(item["opened_at"]) == 32
    assert item["declared_at"] == item["opened_at"]


def test_the_source_alert_is_stored_as_a_message_map() -> None:
    """The source alert names the alert's conversation and message; the url hint is kept when present."""
    assert incident_item(_full())["source_alert"] == {
        "system": "slack",
        "tenant": "T0TENANT",
        "conversation_id": "C0ALERTS",
        "message_id": "1760536800.000100",
        "url": "https://slack.test/archives/C0ALERTS/p1760536800000100",
    }


def test_a_reference_without_a_url_is_stored_without_one() -> None:
    """The url is an optional hint: absent, never stored as None."""
    alert = MessageReference(system=WorkplaceSystem.SLACK, tenant="T0TENANT", conversation_id="C0ALERTS", message_id="1.2")

    item = incident_item(_minimal(source_alert=alert))

    assert item["source_alert"] == {"system": "slack", "tenant": "T0TENANT", "conversation_id": "C0ALERTS", "message_id": "1.2"}
    assert "url" not in item["conversation"]


@pytest.mark.parametrize("incident", [_minimal(conversation=None), _minimal(), _full()], ids=["no-surface", "minimal", "full"])
def test_the_stored_item_reads_back_as_the_same_incident(incident: Incident) -> None:
    """Writer and parser agree on every field and reference kind; times come back equal in UTC."""
    result = parse_incident_item(incident_item(incident))

    assert result.is_success
    assert result.data == incident


@pytest.mark.parametrize(
    "stored",
    [
        {"system": "slack", "tenant": "T0TENANT", "vendor_id": "C0ALERTS"},
        {"system": "slack", "tenant": "T0TENANT", "conversation_id": "C0ALERTS", "message_id": " "},
        {"system": "teams", "tenant": "T0TENANT", "conversation_id": "C0ALERTS", "message_id": "1.2"},
        {"system": "slack", "tenant": "T0TENANT", "conversation_id": "C0ALERTS", "message_id": "1.2", "url": 7},
        "C0ALERTS",
    ],
)
def test_an_unreadable_stored_source_alert_is_dropped_and_logged_without_the_map(stored: object) -> None:
    """An old-shape or broken map reads as no source alert; the incident stays readable and the log omits the map."""
    item = incident_item(_minimal())
    item["source_alert"] = stored

    with capture_logs() as logs:
        result = parse_incident_item(item)

    assert result.data is not None
    assert result.data.source_alert is None
    events = [log for log in logs if log["event"] == "incident_field_unreadable"]
    assert [(log["incident_id"], log["field"]) for log in events] == [(INCIDENT_ID, "source_alert")]
    assert all("value" not in log for log in events)
