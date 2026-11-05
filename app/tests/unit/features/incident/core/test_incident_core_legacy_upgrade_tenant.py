"""Behavior tests for the tenant check of the incident legacy upgrade.

The upgrade stamps the Slack tenant on every conversation reference it writes,
so it asks the host TenantVerifier (a FakeTenantVerifier here) once per run, in
both modes. A mismatch, a failed call or a verified tenant other than the
configured one fails the run before any write, and the report carries the
verifier's status, code and message, which names the expected and received ids.
"""

import pytest

from contracts.operations import OperationResult
from contracts.operations.codes import ErrorCode
from contracts.operations.status import OperationStatus
from contracts.workplace import WorkplaceSystem
from tests.factories.incident import SLACK_TENANT
from tests.factories.legacy_upgrade import legacy_item, legacy_upgrade, records_with, verified_slack
from tests.factories.tenant_verifier import FakeTenantVerifier

pytestmark = pytest.mark.unit

MISMATCH = OperationResult.error(
    OperationStatus.UNAUTHORIZED,
    "Slack tenant mismatch: expected team_id=T0SLACK enterprise_id=None; received team_id=T0OTHER enterprise_id=None",
    ErrorCode.TENANT_MISMATCH,
)
FAILED = OperationResult.error(
    OperationStatus.TRANSIENT_ERROR, "Slack auth.test failed: ratelimited", ErrorCode.TENANT_CHECK_FAILED
)


def test_a_verified_tenant_lets_apply_proceed_after_one_check() -> None:
    verifier = verified_slack()
    records = records_with(legacy_item("inc-1"))

    report = legacy_upgrade(records, verifier=verifier).run(apply=True)

    assert verifier.calls == [WorkplaceSystem.SLACK]
    assert report.tenant_check is not None
    assert (report.tenant_check.outcome, report.tenant_check.tenant) == ("verified", SLACK_TENANT)
    assert report.upgraded == 1


@pytest.mark.parametrize("apply", [True, False])
@pytest.mark.parametrize(("result", "outcome"), [(MISMATCH, "mismatch"), (FAILED, "failed")])
def test_a_mismatch_or_failed_check_fails_the_run_reporting_the_verifier_answer(
    apply: bool, result: OperationResult[str], outcome: str
) -> None:
    records = records_with(legacy_item("inc-1"))

    report = legacy_upgrade(records, verifier=FakeTenantVerifier({WorkplaceSystem.SLACK: result})).run(apply=apply)

    check = report.tenant_check
    assert check is not None
    assert (check.outcome, check.status, check.error_code, check.message) == (
        outcome,
        result.status.value,
        result.error_code,
        result.message,
    )
    assert (report.outcome, report.failures, report.upgraded) == ("failed", ("tenant_check_failed",), 0)
    assert records.writes == []


def test_a_verified_tenant_other_than_the_configured_one_fails_closed() -> None:
    records = records_with(legacy_item("inc-1"))

    report = legacy_upgrade(records, verifier=verified_slack("T0OTHER")).run(apply=True)

    assert report.tenant_check is not None
    assert report.tenant_check.outcome == "mismatch"
    assert report.tenant_check.message is not None and "T0OTHER" in report.tenant_check.message
    assert (report.outcome, records.writes) == ("failed", [])


def test_an_unconfigured_slack_tenant_fails_the_check() -> None:
    records = records_with(legacy_item("inc-1"))

    report = legacy_upgrade(records, verifier=FakeTenantVerifier({})).run(apply=True)

    assert report.tenant_check is not None
    assert (report.tenant_check.outcome, report.tenant_check.error_code) == ("failed", ErrorCode.UNSUPPORTED_OPERATION)
    assert report.outcome == "failed"
