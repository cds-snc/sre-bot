"""Behavior tests for the end-state incident item parser: reference maps.

Pure function tests on plain dicts shaped like stored items. Each reference
kind is one nested map {system, tenant, vendor_id, url}; a map that cannot be
read reads as no reference, the incident stays readable, and the log names the
incident and the field.
"""

from decimal import Decimal
from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.workplace import WorkplaceSystem
from features.incident.core.adapters.incident_items import parse_incident_item
from features.incident.core.domain import (
    ConversationReference,
    ExternalCaseReference,
    Incident,
    PostmortemMeetingReference,
    ReportReference,
    ResourceReference,
    SourceAlertReference,
    VideoCallReference,
)

pytestmark = pytest.mark.unit

INCIDENT_ID = "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11"
KINDS: list[tuple[str, type[ResourceReference]]] = [
    ("conversation", ConversationReference),
    ("report", ReportReference),
    ("video_call", VideoCallReference),
    ("postmortem_meeting", PostmortemMeetingReference),
    ("external_case", ExternalCaseReference),
    ("source_alert", SourceAlertReference),
]
FIELDS = [field for field, _ in KINDS]


def _item(**overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": INCIDENT_ID,
        "record_version": Decimal(1),
        "title": "Notify emails delayed",
        "status": "Open",
        "declared_by": "U0DECLARER",
        "declared_at": "2026-10-15T14:00:00.000000+00:00",
        "security_incident": False,
    }
    item.update(overrides)
    return item


def _map(**overrides: Any) -> dict[str, Any]:
    reference: dict[str, Any] = {"system": "slack", "tenant": "T0TENANT", "vendor_id": "C0INCIDENT"}
    reference.update(overrides)
    return reference


def _read(item: dict[str, Any]) -> Incident:
    result = parse_incident_item(item)
    assert result.is_success
    assert result.data is not None
    return result.data


@pytest.mark.parametrize(("field", "kind"), KINDS)
def test_each_reference_kind_reads_as_its_type(field: str, kind: type[ResourceReference]) -> None:
    """Every kind uses the same map shape and reads as its own reference type, the source alert included."""
    reference = getattr(_read(_item(**{field: _map(url="https://example.test/x")})), field)

    assert type(reference) is kind
    assert reference == kind(
        system=WorkplaceSystem.SLACK, tenant="T0TENANT", vendor_id="C0INCIDENT", url="https://example.test/x"
    )


@pytest.mark.parametrize("field", FIELDS)
def test_the_url_is_optional(field: str) -> None:
    """The url is a hint the owning adapter can re-render, so a map without it is complete."""
    assert getattr(_read(_item(**{field: _map()})), field).url is None


@pytest.mark.parametrize("field", FIELDS)
def test_an_absent_reference_is_none_without_a_log(field: str) -> None:
    with capture_logs() as logs:
        incident = _read(_item())

    assert getattr(incident, field) is None
    assert [log for log in logs if log["event"] == "incident_field_unreadable"] == []


@pytest.mark.parametrize(
    "stored",
    [
        _map(system="teams"),
        _map(system=None),
        _map(tenant=" "),
        _map(vendor_id=""),
        _map(url=7),
        {"system": "slack", "tenant": "T0TENANT"},
        "C0INCIDENT",
        ["slack", "T0TENANT", "C0INCIDENT"],
    ],
)
@pytest.mark.parametrize("field", FIELDS)
def test_an_unreadable_reference_is_no_reference_and_the_incident_stays_readable(field: str, stored: object) -> None:
    """A system that is not a WorkplaceSystem member, a blank tenant or id, or a wrong shape: no reference, logged."""
    with capture_logs() as logs:
        incident = _read(_item(**{field: stored}))

    assert getattr(incident, field) is None
    events = [log for log in logs if log["event"] == "incident_field_unreadable"]
    assert [(log["incident_id"], log["field"]) for log in events] == [(INCIDENT_ID, field)]
