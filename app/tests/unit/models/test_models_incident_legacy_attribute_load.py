"""Loading incident rows that still carry the retired ``incident_updates`` attribute.

Stored incidents keep their ``incident_updates`` list in the table. The legacy
readers load a row with a per-call ``extra="ignore"``, which drops it (and any
other end-state key); strict construction, as ``create_incident`` does, still
refuses every unknown key. The tests build ``Incident`` directly from plain row
values, with no store or Slack involved.
"""

from typing import Any

import pytest
from pydantic import ValidationError

from models.incidents import Incident

pytestmark = pytest.mark.unit


def incident_row(**extra: Any) -> dict[str, Any]:
    """A minimal incident row with every required field, plus ``extra`` keys."""
    return {
        "id": "incident-42",
        "channel_id": "C0INCIDENT",
        "channel_name": "incident-2026-10-08-outage",
        "name": "Outage",
        "user_id": "U0INVOKER",
        "teams": ["sre"],
        "report_url": "https://docs.example.test/report",
        "created_at": "1791472664.0",
        **extra,
    }


@pytest.mark.parametrize(
    "stored_updates", [[], ["2025-01-31 11:17:06 EST\nlegacy update"], None], ids=["empty", "filled", "null"]
)
def test_incident_loads_a_row_carrying_the_legacy_incident_updates_list(stored_updates: list[str] | None) -> None:
    """A row with the legacy list loads, tolerantly, into the same incident as the row without it."""
    incident = Incident.model_validate(incident_row(incident_updates=stored_updates), extra="ignore")

    assert incident == Incident(**incident_row())


@pytest.mark.parametrize("key", ["unexpected_field", "incident_updates"])
def test_strict_construction_rejects_any_unknown_key(key: str) -> None:
    """Strict construction refuses every unexpected key, the retired list included, naming the key."""
    with pytest.raises(ValidationError) as excinfo:
        Incident(**incident_row(**{key: "value"}))

    assert [error["loc"] for error in excinfo.value.errors()] == [(key,)]
    assert [error["type"] for error in excinfo.value.errors()] == ["extra_forbidden"]


def test_incident_dump_has_no_incident_updates_key() -> None:
    """Dumping an incident, including one loaded tolerantly from a legacy row, never writes the legacy list back."""
    loaded_from_legacy_row = Incident.model_validate(incident_row(incident_updates=["legacy update"]), extra="ignore")

    assert "incident_updates" not in Incident(**incident_row()).model_dump()
    assert "incident_updates" not in loaded_from_legacy_row.model_dump()
    assert loaded_from_legacy_row.model_dump()["id"] == "incident-42"
