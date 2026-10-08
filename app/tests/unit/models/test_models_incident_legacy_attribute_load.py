"""Loading incident rows that still carry the retired ``incident_updates`` attribute.

Stored incidents keep their ``incident_updates`` list in the table, so the
model must accept it on load and drop it, while any other unexpected key is
still refused. The tests build ``Incident`` directly from plain row values,
with no store or Slack involved.
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
    """A row with the legacy list loads into the same incident as the row without it."""
    incident = Incident(**incident_row(incident_updates=stored_updates))

    assert incident == Incident(**incident_row())


def test_incident_still_rejects_any_other_unknown_key() -> None:
    """Unexpected keys other than the legacy list keep failing validation, naming the key."""
    with pytest.raises(ValidationError) as excinfo:
        Incident(**incident_row(unexpected_field="value"))

    assert [error["loc"] for error in excinfo.value.errors()] == [("unexpected_field",)]
    assert [error["type"] for error in excinfo.value.errors()] == ["extra_forbidden"]


def test_incident_dump_has_no_incident_updates_key() -> None:
    """Dumping an incident, including one loaded from a legacy row, never writes the legacy list back."""
    loaded_from_legacy_row = Incident(**incident_row(incident_updates=["legacy update"]))

    assert "incident_updates" not in Incident(**incident_row()).model_dump()
    assert "incident_updates" not in loaded_from_legacy_row.model_dump()
    assert loaded_from_legacy_row.model_dump()["id"] == "incident-42"
