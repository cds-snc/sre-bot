"""Behavior tests for the Incident record.

Plain value tests: no store or stub is involved. They pin the record's
invariants: a named, titled incident; enum members (never plain strings) for
status and severity; timezone-aware times; immutability; and None defaults for
everything a legacy item may lack.
"""

import dataclasses
from datetime import UTC, datetime, timedelta, timezone

import pytest

from contracts.workplace import WorkplaceSystem
from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.api import ConversationReference, Incident, IncidentSecurityFlag

pytestmark = pytest.mark.unit

AT = datetime(2026, 10, 15, 14, 0, tzinfo=UTC)


def _incident(**overrides: object) -> Incident:
    fields: dict[str, object] = {
        "id": "7f0c3a52-3d0e-4d55-9a4e-6f1f2b9c0a11",
        "title": "Notify emails delayed",
        "status": IncidentStatus.OPEN,
        "declarer": "U0DECLARER",
        "declared_at": AT,
    }
    fields.update(overrides)
    return Incident(**fields)  # type: ignore[arg-type]


def test_a_new_incident_holds_only_what_was_declared() -> None:
    """Everything beyond the declaration is unset until someone records it."""
    incident = _incident()

    assert incident.product is None
    assert incident.severity is None
    assert incident.security_flag is IncidentSecurityFlag.UNKNOWN
    assert (incident.detected_at, incident.impact_started_at, incident.impact_ended_at) == (None, None, None)
    assert (
        incident.incident_commander,
        incident.operations_lead,
        incident.communications_lead,
        incident.policy_lead,
        incident.postmortem_owner,
    ) == (None, None, None, None, None)
    assert (
        incident.conversation,
        incident.report,
        incident.video_call,
        incident.postmortem_meeting,
        incident.external_case,
        incident.source_alert,
    ) == (None, None, None, None, None, None)


def test_a_full_incident_keeps_every_field() -> None:
    """Roles, timings, severity and references are carried as given; times in any zone are accepted."""
    eastern = timezone(timedelta(hours=-4))
    conversation = ConversationReference(system=WorkplaceSystem.SLACK, tenant="T0TENANT", vendor_id="C0INCIDENT")
    incident = _incident(
        product="GC Notify",
        severity=Severity.SEV1,
        security_flag=IncidentSecurityFlag.NO,
        detected_at=AT,
        impact_started_at=datetime(2026, 10, 15, 9, 0, tzinfo=eastern),
        impact_ended_at=AT,
        incident_commander="U0IC",
        conversation=conversation,
    )

    assert incident.severity is Severity.SEV1
    assert incident.incident_commander == "U0IC"
    assert incident.conversation is conversation


def test_the_record_is_frozen() -> None:
    """The record is an immutable value; a change is a new record."""
    incident = _incident()

    with pytest.raises(dataclasses.FrozenInstanceError):
        incident.title = "edited"  # type: ignore[misc]


@pytest.mark.parametrize("field", ["declared_at", "detected_at", "impact_started_at", "impact_ended_at"])
def test_a_naive_time_is_rejected(field: str) -> None:
    """A time without a zone is ambiguous, so the record refuses it and names the field."""
    with pytest.raises(ValueError, match=field):
        _incident(**{field: datetime(2026, 10, 15, 14, 0)})


@pytest.mark.parametrize("field", ["id", "title"])
def test_a_blank_id_or_title_is_rejected(field: str) -> None:
    """An incident is always addressable and named."""
    with pytest.raises(ValueError, match=field):
        _incident(**{field: "  "})


def test_a_status_must_be_an_incident_status_member() -> None:
    """A plain string is never accepted where a status is chosen; stored values are mapped by the store."""
    with pytest.raises(ValueError, match="status"):
        _incident(status="Open")


def test_a_severity_must_be_a_severity_member_or_unset() -> None:
    """A bare number is never accepted where a severity is chosen."""
    with pytest.raises(ValueError, match="severity"):
        _incident(severity=1)
