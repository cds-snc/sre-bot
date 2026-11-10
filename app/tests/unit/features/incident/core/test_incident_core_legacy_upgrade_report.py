"""Behavior tests for the incident legacy upgrade's report event.

Production cannot run scripts, so the one structured event per run is the only
evidence of what the job did. Logs are captured with structlog's capture_logs;
the event must carry every count, list and the tenant check, log at error when
the run failed, and hold no stored value but an unmatched status.
"""

from typing import Any

import pytest
from structlog.testing import capture_logs

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.workplace import WorkplaceSystem
from tests.factories.legacy_upgrade import MEET_URL, REPORT_URL, end_state_item, legacy_item, legacy_upgrade, records_with
from tests.factories.tenant_verifier import FakeTenantVerifier

pytestmark = pytest.mark.unit

KEYS = {
    "mode",
    "outcome",
    "failures",
    "cap",
    "scanned",
    "already_upgraded",
    "to_upgrade",
    "upgraded",
    "guard_lost",
    "pending",
    "bindings_put",
    "bindings_existing",
    "marker_raised",
    "binding_skipped",
    "unbound",
    "unmatched_status",
    "unreadable",
    "dropped",
    "tenant_check",
}


def _reports(logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [log for log in logs if log["event"] == "incident_legacy_upgrade_report"]


def test_a_successful_run_logs_one_info_event_with_every_key() -> None:
    records = records_with(legacy_item("inc-1"))

    with capture_logs() as logs:
        legacy_upgrade(records).run(apply=True)

    [event] = _reports(logs)
    assert set(event) >= KEYS
    assert (event["log_level"], event["mode"], event["outcome"], event["upgraded"]) == ("info", "apply", "succeeded", 1)
    assert event["tenant_check"]["outcome"] == "verified"


@pytest.mark.parametrize(
    ("records_items", "verifier", "max_items"),
    [
        ([legacy_item("inc-1"), legacy_item("inc-2")], None, 1),
        ([legacy_item("inc-1", status="Resolved")], None, 100),
        (
            [legacy_item("inc-1")],
            FakeTenantVerifier({WorkplaceSystem.SLACK: OperationResult.permanent_error("no", ErrorCode.TENANT_CHECK_FAILED)}),
            100,
        ),
    ],
    ids=["cap", "unreadable", "tenant"],
)
def test_a_failed_run_logs_one_error_event(
    records_items: list[dict[str, Any]], verifier: FakeTenantVerifier | None, max_items: int
) -> None:
    records = records_with(*records_items)

    with capture_logs() as logs:
        legacy_upgrade(records, verifier=verifier, max_items=max_items).run(apply=False)

    [event] = _reports(logs)
    assert set(event) >= KEYS
    assert (event["log_level"], event["mode"], event["outcome"]) == ("error", "dry_run", "failed")


def test_the_event_holds_ids_and_fields_but_no_stored_value_except_the_status() -> None:
    records = records_with(
        legacy_item("inc-status", status="Resolved"),
        legacy_item("inc-name", name=" ", meet_url="https://example.com/secret-room"),
        legacy_item("inc-drop", report_url="https://example.com/private-doc"),
    )

    with capture_logs() as logs:
        legacy_upgrade(records).run(apply=False)

    [event] = _reports(logs)
    text = repr(event)
    assert event["unmatched_status"] == [{"incident_id": "inc-status", "value": "Resolved"}]
    assert event["unreadable"] == [{"incident_id": "inc-name", "field": "name"}]
    assert event["dropped"] == [{"incident_id": "inc-drop", "field": "report_url"}]
    for value in ("private-doc", "secret-room", REPORT_URL, MEET_URL, "U0DECLARER", "Incident inc-", "C0INC"):
        assert value not in text


def test_the_event_counts_the_binding_step_and_names_blocking_items_by_id_only() -> None:
    records = records_with(legacy_item("inc-ok"), legacy_item("inc-open", channel_id=None))

    with capture_logs() as logs:
        legacy_upgrade(records).run(apply=True)

    [event] = _reports(logs)
    assert event["unbound"] == ["inc-open"]
    assert (event["bindings_put"], event["bindings_existing"], event["marker_raised"], event["binding_skipped"]) == (0, 0, 0, 0)
    assert "C0INC-OPEN" not in repr(event)


def test_the_event_of_an_applied_run_counts_puts_and_raises() -> None:
    records = records_with(legacy_item("inc-1"), end_state_item("inc-2"), legacy_item("inc-3", status="Closed", channel_id=None))

    with capture_logs() as logs:
        legacy_upgrade(records).run(apply=True)

    [event] = _reports(logs)
    assert (event["bindings_put"], event["marker_raised"], event["binding_skipped"], event["unbound"]) == (2, 1, 1, [])
