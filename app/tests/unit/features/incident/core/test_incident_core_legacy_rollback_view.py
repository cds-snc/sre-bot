"""Behavior tests for legacy_view, the new-first overlay the legacy readers validate.

Items come from the real upgrade plan, read back with DynamoDB number typing,
so the shapes are the ones an upgraded item really has. The overlay must let the
legacy Incident model validate them under per-call extra="ignore", while strict
construction still refuses unknown keys.
"""

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from features.incident.core.adapters.legacy_rollback import legacy_view
from models.incidents import Incident
from tests.factories.legacy_rollback import upgraded_item
from tests.factories.legacy_upgrade import legacy_item

pytestmark = pytest.mark.unit


def _legacy(item: dict[str, Any]) -> Incident:
    return Incident.model_validate(legacy_view(item), extra="ignore")


def test_an_upgraded_item_validates_as_the_legacy_incident() -> None:
    incident = _legacy(upgraded_item())

    assert (incident.id, incident.status, incident.severity) == ("inc-1", "Open", "sev-2")
    assert incident.name == "Incident inc-1"


def test_strict_construction_still_rejects_the_end_state_keys() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Incident(**upgraded_item())

    assert "extra_forbidden" in {error["type"] for error in excinfo.value.errors()}


@pytest.mark.parametrize("severity", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("kind", [int, Decimal])
def test_an_integer_severity_renders_as_the_legacy_string(severity: int, kind: type) -> None:
    item = {**upgraded_item(), "severity": kind(severity)}

    assert legacy_view(item)["severity"] == f"sev-{severity}"


def test_an_absent_or_legacy_severity_is_left_as_it_is() -> None:
    item = upgraded_item()
    del item["severity"]
    assert "severity" not in legacy_view(item)
    assert legacy_view({**item, "severity": "sev-3"})["severity"] == "sev-3"


@pytest.mark.parametrize("severity", [True, 7, Decimal("2.5"), -1])
def test_a_severity_that_is_not_a_level_is_not_rendered(severity: object) -> None:
    assert legacy_view({**upgraded_item(), "severity": severity})["severity"] == severity


def test_stored_times_render_as_the_epoch_text_the_legacy_view_parses() -> None:
    view = legacy_view(upgraded_item())

    assert [int(float(view[name])) for name in ("detection_time", "start_impact_time")] == [1760536700, 1760536600]
    assert view["end_impact_time"] == "Unknown"


def test_a_stored_time_wins_over_the_legacy_attribute_and_the_legacy_one_is_the_fallback() -> None:
    item = upgraded_item()
    item["impact_ended_at"] = "2025-10-15T15:00:00.000000+00:00"
    item.pop("detected_at")

    view = legacy_view(item)

    assert int(float(view["end_impact_time"])) == 1760540400
    assert view["detection_time"] == "1760536700"


def test_title_and_reference_urls_win_when_present_and_the_legacy_attributes_are_the_fallback() -> None:
    item = upgraded_item()
    item["title"] = "Renamed"
    item["report"] = {"kind": "report", "url": "https://docs.example.test/new"}
    item["video_call"] = {"kind": "video_call", "url": "https://meet.example.test/new"}
    view = legacy_view(item)
    assert (view["name"], view["report_url"], view["meet_url"]) == (
        "Renamed",
        "https://docs.example.test/new",
        "https://meet.example.test/new",
    )

    for attribute in ("title", "report", "video_call"):
        del item[attribute]
    view = legacy_view(item)
    assert (view["name"], view["report_url"]) == ("Incident inc-1", item["report_url"])


def test_a_reference_without_a_url_keeps_the_legacy_attribute() -> None:
    item = {**upgraded_item(), "report": {"kind": "report"}}

    assert legacy_view(item)["report_url"] == item["report_url"]


def test_a_legacy_item_passes_through_unchanged() -> None:
    item = legacy_item("inc-9")

    assert legacy_view(item) == item
    assert legacy_view(item) is not item


def test_an_unparseable_stored_time_keeps_the_legacy_attribute() -> None:
    item = {**upgraded_item(), "detected_at": "not a time"}

    assert legacy_view(item)["detection_time"] == item["detection_time"]
