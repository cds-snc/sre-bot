"""Round trips across the rollback guard with the real item shapes.

An item is upgraded by the real plan, then changed either by a legacy translated
write (read back by the end-state parser) or by a rebuilt writer's attribute
change (read back by the legacy view). Nothing here touches infrastructure.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from boto3.dynamodb.types import TypeDeserializer

from features.incident.common.vocabulary import IncidentStatus, Severity
from features.incident.core.adapters.incident_items import parse_incident_item
from features.incident.core.adapters.legacy_rollback import TranslatedUpdate, legacy_view, translated_update
from models.incidents import Incident
from tests.factories.legacy_rollback import through_dynamodb, upgraded_item

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def _apply(item: dict[str, Any], update: TranslatedUpdate) -> dict[str, Any]:
    deserialize = TypeDeserializer().deserialize
    changed = dict(item)
    changed.update({name: deserialize(value) for name, value in update.sets.items()})
    for name, value in update.sets_if_absent.items():
        changed.setdefault(name, deserialize(value))
    for name in update.removes:
        changed.pop(name, None)
    return changed


def _legacy_write(item: dict[str, Any], field: str, value: str) -> dict[str, Any]:
    update = translated_update(field, value, marker=2, now=NOW)
    assert update is not None
    return _apply(item, update)


def test_a_legacy_severity_write_is_read_by_the_end_state_parser() -> None:
    written = _legacy_write(upgraded_item(), "severity", "sev-4")

    parsed = parse_incident_item(written)

    assert parsed.is_success and parsed.data is not None
    assert parsed.data.severity is Severity.SEV4
    assert isinstance(written["severity"], Decimal)


def test_a_legacy_no_severity_write_is_read_as_no_severity() -> None:
    parsed = parse_incident_item(_legacy_write(upgraded_item(), "severity", "none"))

    assert parsed.data is not None
    assert parsed.data.severity is None


def test_a_legacy_time_write_is_read_by_the_end_state_parser() -> None:
    written = _legacy_write(upgraded_item(), "end_impact_time", "1760540400.0")

    parsed = parse_incident_item(written)

    assert parsed.data is not None
    assert parsed.data.impact_ended_at == datetime(2025, 10, 15, 15, 0, tzinfo=UTC)


def test_a_legacy_close_takes_the_incident_off_the_open_index_and_a_reopen_puts_it_back() -> None:
    closed = _legacy_write(upgraded_item(), "status", "Closed")
    assert {"open_bucket", "opened_at"}.isdisjoint(closed)
    parsed = parse_incident_item(closed)
    assert parsed.data is not None and parsed.data.status is IncidentStatus.CLOSED
    assert not parsed.data.status.is_open

    reopened = _legacy_write(closed, "status", "In Progress")
    assert reopened["open_bucket"] == "OPEN"
    assert reopened["opened_at"] == "2026-11-10T12:00:00.000000+00:00"
    parsed = parse_incident_item(reopened)
    assert parsed.data is not None and parsed.data.status.is_open


def test_a_legacy_status_write_keeps_the_original_opened_at() -> None:
    item = upgraded_item()

    written = _legacy_write(item, "status", "In Progress")

    assert written["opened_at"] == item["opened_at"]


def test_a_rebuilt_writer_change_is_read_by_the_legacy_view() -> None:
    item = upgraded_item()
    item.update(
        through_dynamodb({"severity": 1, "title": "Rebuilt title", "impact_started_at": "2025-10-15T13:00:00.000000+00:00"})
    )

    incident = Incident.model_validate(legacy_view(item), extra="ignore")

    assert (incident.severity, incident.name) == ("sev-1", "Rebuilt title")
    assert int(float(incident.start_impact_time)) == 1760533200
