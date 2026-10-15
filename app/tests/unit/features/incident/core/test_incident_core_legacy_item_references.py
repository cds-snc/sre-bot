"""Behavior tests for the legacy item bridge: references and their tenants.

A legacy item stores bare vendor ids and links; the end state stores one
reference map per kind with the configured tenant of its system, passed in by
the caller. A present value whose system has no configured tenant is
unreadable rather than dropped, so an upgrade never stamps over a lost
reference. A malformed report or Meet link is dropped and logged without the
link itself.
"""

from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.incident_items import parse_incident_item
from features.incident.core.adapters.legacy_items import UnreadableLegacyItem, UpgradedItem, upgrade_legacy_item
from features.incident.core.domain import ConversationReference, Incident, ReportReference, VideoCallReference

pytestmark = pytest.mark.unit

INCIDENT_ID = "inc-legacy"
SLACK_TENANT = "T0SLACK"
GOOGLE_TENANT = "C0GOOGLE"
TENANTS = {WorkplaceSystem.SLACK: SLACK_TENANT, WorkplaceSystem.GOOGLE: GOOGLE_TENANT}
REPORT_URL = "https://docs.google.com/document/d/1AbC-dEf_123/edit"
MEET_URL = "https://meet.google.com/abc-defg-hij"


def _legacy(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": INCIDENT_ID,
        "name": "Notify emails delayed",
        "user_id": "U0DECLARER",
        "status": "Open",
        "created_at": "1760536800",
    }
    item.update(overrides)
    return item


def _read(item: dict[str, Any], tenants: dict[WorkplaceSystem, str] | None = None) -> Incident:
    upgraded = upgrade_legacy_item(item, TENANTS if tenants is None else tenants)
    assert isinstance(upgraded, UpgradedItem)
    parsed = parse_incident_item(upgraded.item)
    assert parsed.data is not None
    return parsed.data


def _dropped(logs: list[dict[str, Any]]) -> list[tuple[object, str]]:
    return [(log["incident_id"], log["field"]) for log in logs if log["event"] == "incident_legacy_field_dropped"]


def test_the_channel_is_the_slack_conversation_of_the_configured_tenant() -> None:
    assert _read(_legacy(channel_id="C0INCIDENT")).conversation == ConversationReference(
        system=WorkplaceSystem.SLACK, tenant=SLACK_TENANT, vendor_id="C0INCIDENT"
    )


def test_the_report_link_is_the_google_report_with_its_document_id() -> None:
    assert _read(_legacy(report_url=REPORT_URL)).report == ReportReference(
        system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="1AbC-dEf_123", url=REPORT_URL
    )


@pytest.mark.parametrize("meet_url", [MEET_URL, f"{MEET_URL}?authuser=0", f"{MEET_URL}/"])
def test_the_meet_link_is_the_google_video_call_with_its_meet_code(meet_url: str) -> None:
    assert _read(_legacy(meet_url=meet_url)).video_call == VideoCallReference(
        system=WorkplaceSystem.GOOGLE, tenant=GOOGLE_TENANT, vendor_id="abc-defg-hij", url=meet_url
    )


@pytest.mark.parametrize("overrides", [{"channel_id": ""}, {"report_url": ""}, {"meet_url": "TBC"}, {"meet_url": ""}, {}])
def test_a_blank_or_placeholder_value_is_no_reference_without_a_log(overrides: dict[str, Any]) -> None:
    item = _legacy(**overrides)
    item.setdefault("meet_url", None)

    with capture_logs() as logs:
        incident = _read(item)

    assert (incident.conversation, incident.report, incident.video_call) == (None, None, None)
    assert _dropped(logs) == []


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"report_url": "https://docs.google.com/spreadsheets/u/0/edit"}, "report_url"),
        ({"report_url": "not a link"}, "report_url"),
        ({"meet_url": "https://zoom.us/j/123"}, "meet_url"),
        ({"meet_url": "https://meet.google.com/"}, "meet_url"),
    ],
)
def test_a_malformed_link_is_dropped_and_logged_without_the_link(overrides: dict[str, Any], field: str) -> None:
    with capture_logs() as logs:
        incident = _read(_legacy(**overrides))

    assert (incident.report, incident.video_call) == (None, None)
    assert _dropped(logs) == [(INCIDENT_ID, field)]
    link = overrides[field]
    assert all(link not in str(log.values()) for log in logs)


@pytest.mark.parametrize(
    ("overrides", "tenants", "field"),
    [
        ({"channel_id": "C0INCIDENT"}, {WorkplaceSystem.GOOGLE: GOOGLE_TENANT}, "channel_id"),
        ({"report_url": REPORT_URL}, {WorkplaceSystem.SLACK: SLACK_TENANT}, "report_url"),
        ({"meet_url": MEET_URL}, {WorkplaceSystem.SLACK: SLACK_TENANT}, "meet_url"),
    ],
)
def test_a_reference_without_a_configured_tenant_is_unreadable(
    overrides: dict[str, Any], tenants: dict[WorkplaceSystem, str], field: str
) -> None:
    upgraded = upgrade_legacy_item(_legacy(**overrides), tenants)

    assert isinstance(upgraded, UnreadableLegacyItem)
    assert (upgraded.incident_id, upgraded.field) == (INCIDENT_ID, field)


def test_no_tenant_is_needed_when_the_item_holds_no_reference() -> None:
    assert _read(_legacy(meet_url="TBC"), tenants={}).conversation is None


def test_a_malformed_link_needs_no_tenant() -> None:
    """The link is dropped either way, so a missing tenant does not make the item unreadable."""
    assert _read(_legacy(report_url="not a link"), tenants={}).report is None
