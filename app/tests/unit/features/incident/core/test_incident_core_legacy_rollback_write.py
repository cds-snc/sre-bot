"""Behavior tests for translated_update, the legacy field write on a marker-2 item.

The translation is pure: it names the end-state attributes to set or remove for
one legacy field, or nothing when the item carries no marker or the field has
no end-state counterpart.
"""

from datetime import UTC, datetime

import pytest

from features.incident.core.adapters.legacy_rollback import UntranslatableValueError, translated_update

pytestmark = pytest.mark.unit

NOW = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)
NOW_STORED = "2026-11-10T12:00:00.000000+00:00"


def test_an_item_without_the_marker_is_not_translated() -> None:
    assert translated_update("severity", "sev-3", marker=None, now=NOW) is None


@pytest.mark.parametrize("field", ["retrospective_url", "name", "report_url"])
def test_a_field_without_an_end_state_counterpart_is_not_translated(field: str) -> None:
    assert translated_update(field, "value", marker=2, now=NOW) is None


@pytest.mark.parametrize("marker", [2, 3])
def test_a_severity_is_stored_as_the_integer_level(marker: int) -> None:
    update = translated_update("severity", "sev-3", marker=marker, now=NOW)

    assert update is not None
    assert (update.sets, update.removes) == ({"severity": {"N": "3"}}, ())


@pytest.mark.parametrize("value", ["none", "None", " "])
def test_no_severity_removes_the_attribute(value: str) -> None:
    update = translated_update("severity", value, marker=2, now=NOW)

    assert update is not None
    assert (update.sets, update.removes) == ({}, ("severity",))


@pytest.mark.parametrize(
    ("field", "attribute"),
    [("detection_time", "detected_at"), ("start_impact_time", "impact_started_at"), ("end_impact_time", "impact_ended_at")],
)
def test_an_epoch_time_is_stored_as_iso_utc_under_the_new_name(field: str, attribute: str) -> None:
    update = translated_update(field, "1760540400.0", marker=2, now=NOW)

    assert update is not None
    assert update.sets == {attribute: {"S": "2025-10-15T15:00:00.000000+00:00"}}


@pytest.mark.parametrize(("field", "value"), [("severity", "critical"), ("detection_time", "soon"), ("status", "Archived")])
def test_a_value_that_cannot_be_translated_is_refused(field: str, value: str) -> None:
    with pytest.raises(UntranslatableValueError):
        translated_update(field, value, marker=2, now=NOW)


def test_closing_removes_the_open_index() -> None:
    update = translated_update("status", "Closed", marker=2, now=NOW)

    assert update is not None
    assert (update.sets, update.removes, update.sets_if_absent) == ({"status": {"S": "Closed"}}, ("open_bucket", "opened_at"), {})


def test_any_other_status_keeps_the_open_index_and_keeps_an_existing_opened_at() -> None:
    update = translated_update("status", "In Progress", marker=2, now=NOW)

    assert update is not None
    assert update.sets == {"status": {"S": "In Progress"}, "open_bucket": {"S": "OPEN"}}
    assert (update.removes, update.sets_if_absent) == ((), {"opened_at": {"S": NOW_STORED}})


def test_the_update_expression_names_every_set_remove_and_if_absent_attribute() -> None:
    update = translated_update("status", "Open", marker=2, now=NOW)
    assert update is not None

    expression, names, values = update.expression()

    assert expression == "SET #status = :status, #open_bucket = :open_bucket, #opened_at = if_not_exists(#opened_at, :opened_at)"
    assert names == {"#status": "status", "#open_bucket": "open_bucket", "#opened_at": "opened_at"}
    assert values == {":status": {"S": "Open"}, ":open_bucket": {"S": "OPEN"}, ":opened_at": {"S": NOW_STORED}}


def test_the_update_expression_removes_after_the_sets() -> None:
    update = translated_update("status", "Closed", marker=2, now=NOW)
    assert update is not None

    expression, names, values = update.expression()

    assert expression == "SET #status = :status REMOVE #open_bucket, #opened_at"
    assert names == {"#status": "status", "#open_bucket": "open_bucket", "#opened_at": "opened_at"}
    assert values == {":status": {"S": "Closed"}}
