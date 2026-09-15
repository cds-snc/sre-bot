"""Unit tests for AWS account health handler."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import BotoCoreError, ClientError
from freezegun import freeze_time

from infrastructure.operations import OperationResult, OperationStatus
from modules.aws import aws_account_health
from packages.aws_platform.adapters.config import ConfigAdapter
from packages.aws_platform.adapters.cost_explorer import CostExplorerAdapter
from packages.aws_platform.adapters.guard_duty import GuardDutyAdapter
from packages.aws_platform.adapters.organizations import OrganizationsAdapter
from packages.aws_platform.adapters.security_hub import SecurityHubAdapter

ACCOUNT_ID = "123456789012"
ENGLISH_RETRY = "Please try again later."
FRENCH_RETRY = "Veuillez réessayer plus tard."


def _logged(mock_logger: MagicMock, event: str) -> list[dict[str, Any]]:
    """Return the keyword arguments of every log call for ``event``, whether made on the logger or a bound child."""
    return [dict(entry.kwargs) for entry in mock_logger.mock_calls if entry.args[:1] == (event,)]


def _logged_failure(mock_logger: MagicMock, event: str, status: str) -> bool:
    """Whether ``event`` was logged carrying the classified status, an error code and the adapter message."""
    return any(
        kwargs.get("status") == status and kwargs.get("error_code") is not None and kwargs.get("error") is not None
        for kwargs in _logged(mock_logger, event)
    )


def _failure(
    status: OperationStatus = OperationStatus.UNAUTHORIZED,
    error_code: str = "AccessDeniedException",
    message: str = "access denied",
) -> OperationResult[Any]:
    """Return a classified adapter failure."""
    return OperationResult.error(status, message=message, error_code=error_code)


def _cost_entry(amount: str) -> dict[str, Any]:
    """Return one Cost Explorer ResultsByTime entry holding a single linked-account group."""
    return {"Groups": [{"Keys": [ACCOUNT_ID], "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}}}]}


def _client_error(code: str = "AccessDenied", operation: str = "AssumeRole") -> ClientError:
    """Return a botocore ClientError carrying ``code``."""
    return ClientError({"Error": {"Code": code, "Message": "denied"}}, operation)


def _view_text(view: dict[str, Any]) -> str:
    """Concatenate every mrkdwn/plain text section of a Slack modal."""
    return "\n".join(block.get("text", {}).get("text", "") for block in view["blocks"])


def _health(
    last_amount: str | None = "1,234.56",
    current_amount: str | None = "5.00",
    config: Any = 0,
    guardduty: Any = 3,
    securityhub: Any = 0,
) -> dict[str, Any]:
    """Return the get_account_health data shape the modal renders."""
    return {
        "account_id": ACCOUNT_ID,
        "cost": {
            "last_month": {"start_date": "2024-11-01", "end_date": "2024-11-30", "amount": last_amount},
            "current_month": {"start_date": "2024-12-01", "end_date": "2024-12-31", "amount": current_amount},
        },
        "security": {"config": config, "guardduty": guardduty, "securityhub": securityhub},
    }


@pytest.fixture
def health_adapters():
    """Patch the four adapter factories used by get_account_health with spec'd, successful doubles.

    Defaults: one cost group of 1234.5, two non-compliant Config rules, one
    detector with one HIGH finding and no Security Hub findings. Tests override
    single methods to exercise one branch at a time.
    """
    with (
        patch("modules.aws.aws_account_health.build_cost_explorer_adapter") as build_cost_explorer,
        patch("modules.aws.aws_account_health.build_config_adapter") as build_config,
        patch("modules.aws.aws_account_health.build_guard_duty_adapter") as build_guard_duty,
        patch("modules.aws.aws_account_health.build_security_hub_adapter") as build_security_hub,
    ):
        cost_explorer = MagicMock(spec=CostExplorerAdapter)
        cost_explorer.get_cost_and_usage.return_value = OperationResult.success(data=[_cost_entry("1234.5")])
        build_cost_explorer.return_value = cost_explorer

        config = MagicMock(spec=ConfigAdapter)
        config.describe_aggregate_compliance_by_config_rules.return_value = OperationResult.success(data=[{}, {}])
        build_config.return_value = config

        guard_duty = MagicMock(spec=GuardDutyAdapter)
        guard_duty.list_detectors.return_value = OperationResult.success(data=["detector-1"])
        guard_duty.get_findings_statistics.return_value = OperationResult.success(data={"HIGH": 1})
        build_guard_duty.return_value = guard_duty

        security_hub = MagicMock(spec=SecurityHubAdapter)
        security_hub.get_findings.return_value = OperationResult.success(data=[])
        build_security_hub.return_value = security_hub

        yield SimpleNamespace(
            build_cost_explorer=build_cost_explorer,
            build_config=build_config,
            build_guard_duty=build_guard_duty,
            build_security_hub=build_security_hub,
            cost_explorer=cost_explorer,
            config=config,
            guard_duty=guard_duty,
            security_hub=security_hub,
        )


@pytest.fixture
def view_body() -> dict[str, Any]:
    """Return an aws_health_view submission selecting one account."""
    return {
        "view": {
            "state": {
                "values": {
                    "account": {
                        "account": {"selected_option": {"value": ACCOUNT_ID, "text": {"text": f"TestAccount ({ACCOUNT_ID})"}}}
                    }
                }
            }
        },
        "trigger_id": "trigger-123",
    }


@pytest.fixture
def slack_client() -> MagicMock:
    """Return a Slack client double whose views_open reports a view id."""
    client = MagicMock()
    client.views_open.return_value = {"view": {"id": "view-123"}}
    return client


# -- get_account_health ---------------------------------------------------------


@pytest.mark.unit
@freeze_time("2024-12-15")
def test_should_build_each_adapter_once_and_aggregate_health_data(health_adapters):
    """One health check builds each adapter once and aggregates every lookup into the modal data.

    Stub strategy: the patched factories return spec'd adapters with successful
    results. The factory call counts prove Cost Explorer is shared by both months
    rather than assuming a role once per lookup.
    """
    # Act
    result = aws_account_health.get_account_health(ACCOUNT_ID)

    # Assert
    assert result == {
        "account_id": ACCOUNT_ID,
        "cost": {
            "last_month": {"start_date": "2024-11-01", "end_date": "2024-11-30", "amount": "1,234.50"},
            "current_month": {"start_date": "2024-12-01", "end_date": "2024-12-31", "amount": "1,234.50"},
        },
        "security": {"config": 2, "guardduty": 1, "securityhub": 0},
    }
    for build in (
        health_adapters.build_cost_explorer,
        health_adapters.build_config,
        health_adapters.build_guard_duty,
        health_adapters.build_security_hub,
    ):
        build.assert_called_once_with()
    assert health_adapters.cost_explorer.get_cost_and_usage.call_count == 2


@pytest.mark.unit
@pytest.mark.parametrize(
    ("frozen_at", "last_period", "current_period", "last_end_displayed", "current_end_displayed"),
    [
        (
            "2024-12-15",
            {"Start": "2024-11-01", "End": "2024-12-01"},
            {"Start": "2024-12-01", "End": "2025-01-01"},
            "2024-11-30",
            "2024-12-31",
        ),
        (
            "2024-03-10",
            {"Start": "2024-02-01", "End": "2024-03-01"},
            {"Start": "2024-03-01", "End": "2024-04-01"},
            "2024-02-29",
            "2024-03-31",
        ),
    ],
    ids=["year-rollover", "leap-february"],
)
def test_should_query_cost_explorer_with_exclusive_end_and_display_last_day(
    health_adapters, frozen_at, last_period, current_period, last_end_displayed, current_end_displayed
):
    """Cost Explorer receives the first day of the next month as End, while the modal data keeps the last day.

    Stub strategy: time is frozen at a year rollover and in a leap-year March.
    Cost Explorer's End is exclusive, so passing the month's last day would drop
    that day's cost; the displayed range stays human-readable.
    """
    # Act
    with freeze_time(frozen_at):
        result = aws_account_health.get_account_health(ACCOUNT_ID)

    # Assert
    periods = [call.kwargs["time_period"] for call in health_adapters.cost_explorer.get_cost_and_usage.call_args_list]
    assert periods == [last_period, current_period]
    assert result["cost"]["last_month"]["start_date"] == last_period["Start"]
    assert result["cost"]["last_month"]["end_date"] == last_end_displayed
    assert result["cost"]["current_month"]["start_date"] == current_period["Start"]
    assert result["cost"]["current_month"]["end_date"] == current_end_displayed


@pytest.mark.unit
@freeze_time("2024-12-15")
def test_should_keep_other_fields_when_one_lookup_fails(health_adapters):
    """A failed Security Hub lookup marks only that field unavailable; every other field is still collected.

    Stub strategy: only get_findings returns a classified failure.
    """
    # Arrange
    health_adapters.security_hub.get_findings.return_value = _failure(error_code="InvalidAccessException")

    # Act
    result = aws_account_health.get_account_health(ACCOUNT_ID)

    # Assert
    assert result["security"] == {"config": 2, "guardduty": 1, "securityhub": None}
    assert result["cost"]["last_month"]["amount"] == "1,234.50"


# -- get_account_spend ----------------------------------------------------------


@pytest.mark.unit
def test_should_return_formatted_spend_for_the_linked_account():
    """The first group's UnblendedCost is formatted with thousands separators and two decimals.

    Stub strategy: a spec'd Cost Explorer adapter returns one ResultsByTime entry;
    the call arguments are asserted because the adapter names the filter
    ``filter_expression`` and the query must stay scoped to one linked account.
    """
    # Arrange
    adapter = MagicMock(spec=CostExplorerAdapter)
    adapter.get_cost_and_usage.return_value = OperationResult.success(data=[_cost_entry("1234.567")])

    # Act
    result = aws_account_health.get_account_spend(adapter, ACCOUNT_ID, "2024-11-01", "2024-12-01")

    # Assert
    assert result == "1,234.57"
    adapter.get_cost_and_usage.assert_called_once_with(
        time_period={"Start": "2024-11-01", "End": "2024-12-01"},
        granularity="MONTHLY",
        metrics=["UnblendedCost"],
        filter_expression={"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [ACCOUNT_ID]}},
        group_by=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    "results_by_time",
    [[], [{}], [{"Groups": []}]],
    ids=["no-entries", "entry-without-groups", "empty-groups"],
)
def test_should_return_zero_spend_when_no_cost_groups(results_by_time):
    """No cost group, including an empty ResultsByTime list, reports 0.00 instead of raising.

    Stub strategy: a successful Cost Explorer result with each empty shape the
    adapter can return.
    """
    # Arrange
    adapter = MagicMock(spec=CostExplorerAdapter)
    adapter.get_cost_and_usage.return_value = OperationResult.success(data=results_by_time)

    # Act
    result = aws_account_health.get_account_spend(adapter, ACCOUNT_ID, "2024-11-01", "2024-12-01")

    # Assert
    assert result == "0.00"


@pytest.mark.unit
@patch("modules.aws.aws_account_health.logger")
def test_should_return_none_and_log_when_cost_lookup_fails(mock_logger):
    """A failed Cost Explorer lookup yields None (unavailable) and is logged with its classification.

    Stub strategy: get_cost_and_usage returns a classified TRANSIENT failure.
    """
    # Arrange
    adapter = MagicMock(spec=CostExplorerAdapter)
    adapter.get_cost_and_usage.return_value = _failure(OperationStatus.TRANSIENT_ERROR, "ThrottlingException")

    # Act
    result = aws_account_health.get_account_spend(adapter, ACCOUNT_ID, "2024-11-01", "2024-12-01")

    # Assert
    assert result is None
    assert _logged_failure(mock_logger, "aws_health_cost_lookup_failed", "transient_error")


# -- get_config_summary ---------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(("rules", "expected"), [([], 0), ([{"ConfigRuleName": "a"}, {"ConfigRuleName": "b"}], 2)])
def test_should_count_non_compliant_config_rules(rules, expected):
    """The Config summary is the number of non-compliant rules in the Control Tower aggregator for the account.

    Stub strategy: a spec'd Config adapter returns the flattened rule list.
    """
    # Arrange
    adapter = MagicMock(spec=ConfigAdapter)
    adapter.describe_aggregate_compliance_by_config_rules.return_value = OperationResult.success(data=rules)

    # Act
    result = aws_account_health.get_config_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result == expected
    adapter.describe_aggregate_compliance_by_config_rules.assert_called_once_with(
        "aws-controltower-GuardrailsComplianceAggregator",
        {"AccountId": ACCOUNT_ID, "ComplianceType": "NON_COMPLIANT"},
    )


@pytest.mark.unit
@patch("modules.aws.aws_account_health.logger")
def test_should_return_none_and_log_when_config_lookup_fails(mock_logger):
    """A failed Config lookup yields None (unavailable) rather than a misleading count, and is logged.

    Stub strategy: the aggregator is missing, classified NOT_FOUND by the adapter.
    """
    # Arrange
    adapter = MagicMock(spec=ConfigAdapter)
    adapter.describe_aggregate_compliance_by_config_rules.return_value = _failure(
        OperationStatus.NOT_FOUND, "NoSuchConfigurationAggregatorException"
    )

    # Act
    result = aws_account_health.get_config_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result is None
    assert _logged_failure(mock_logger, "aws_health_config_lookup_failed", "not_found")


# -- get_guardduty_summary ------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize(("count_by_severity", "expected"), [({}, 0), ({"LOW": 0, "MEDIUM": 1, "HIGH": 2}, 3)])
def test_should_sum_unarchived_high_severity_guardduty_findings(count_by_severity, expected):
    """The GuardDuty summary sums CountBySeverity for the first detector, filtered to unarchived high findings.

    Stub strategy: a spec'd GuardDuty adapter returns one detector and a
    CountBySeverity dict; the criteria are asserted so the archived filter
    carries a single "false" value.
    """
    # Arrange
    adapter = MagicMock(spec=GuardDutyAdapter)
    adapter.list_detectors.return_value = OperationResult.success(data=["detector-1", "detector-2"])
    adapter.get_findings_statistics.return_value = OperationResult.success(data=count_by_severity)

    # Act
    result = aws_account_health.get_guardduty_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result == expected
    adapter.get_findings_statistics.assert_called_once()
    call = adapter.get_findings_statistics.call_args
    detector_id = call.kwargs.get("detector_id", call.args[0] if call.args else None)
    criteria = call.kwargs.get("finding_criteria", call.args[1] if len(call.args) > 1 else None)
    assert detector_id == "detector-1"
    assert criteria == {
        "Criterion": {
            "accountId": {"Eq": [ACCOUNT_ID]},
            "service.archived": {"Eq": ["false"]},
            "severity": {"Gte": 7},
        }
    }


@pytest.mark.unit
@patch("modules.aws.aws_account_health.logger")
def test_should_report_guardduty_not_enabled_when_no_detectors(mock_logger):
    """An account with no GuardDuty detector is reported as not enabled, without querying statistics.

    Stub strategy: list_detectors succeeds with an empty list, which previously
    raised IndexError.
    """
    # Arrange
    adapter = MagicMock(spec=GuardDutyAdapter)
    adapter.list_detectors.return_value = OperationResult.success(data=[])

    # Act
    result = aws_account_health.get_guardduty_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result == "not_enabled"
    adapter.get_findings_statistics.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.aws_account_health.logger")
def test_should_return_none_and_log_when_guardduty_detectors_lookup_fails(mock_logger):
    """A failed detector listing yields None (unavailable), is logged, and skips the statistics call.

    Stub strategy: list_detectors returns a classified TRANSIENT failure.
    """
    # Arrange
    adapter = MagicMock(spec=GuardDutyAdapter)
    adapter.list_detectors.return_value = _failure(OperationStatus.TRANSIENT_ERROR, "InternalServerErrorException")

    # Act
    result = aws_account_health.get_guardduty_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result is None
    adapter.get_findings_statistics.assert_not_called()
    assert _logged_failure(mock_logger, "aws_health_guardduty_detectors_failed", "transient_error")


@pytest.mark.unit
@patch("modules.aws.aws_account_health.logger")
def test_should_return_none_and_log_when_guardduty_statistics_lookup_fails(mock_logger):
    """A failed statistics call yields None (unavailable) and is logged with the detector it targeted.

    Stub strategy: list_detectors succeeds and get_findings_statistics returns a
    classified UNAUTHORIZED failure.
    """
    # Arrange
    adapter = MagicMock(spec=GuardDutyAdapter)
    adapter.list_detectors.return_value = OperationResult.success(data=["detector-1"])
    adapter.get_findings_statistics.return_value = _failure()

    # Act
    result = aws_account_health.get_guardduty_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result is None
    assert _logged_failure(mock_logger, "aws_health_guardduty_statistics_failed", "unauthorized")
    assert any(
        kwargs.get("detector_id") == "detector-1" for kwargs in _logged(mock_logger, "aws_health_guardduty_statistics_failed")
    )


# -- get_securityhub_summary ----------------------------------------------------


@pytest.mark.unit
def test_should_count_security_hub_findings():
    """The Security Hub summary is the number of findings in the adapter's flat list, queried with the ignore list.

    Stub strategy: a spec'd Security Hub adapter returns three findings across
    what were pages in the legacy shape.
    """
    # Arrange
    adapter = MagicMock(spec=SecurityHubAdapter)
    adapter.get_findings.return_value = OperationResult.success(data=[{"Id": "1"}, {"Id": "2"}, {"Id": "3"}])

    # Act
    result = aws_account_health.get_securityhub_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result == 3
    filters = adapter.get_findings.call_args.args[0] if adapter.get_findings.call_args.args else None
    filters = filters or adapter.get_findings.call_args.kwargs["filters"]
    assert filters["AwsAccountId"] == [{"Value": ACCOUNT_ID, "Comparison": "EQUALS"}]
    assert filters["Title"] == aws_account_health.get_ignored_security_hub_issues()


@pytest.mark.unit
@patch("modules.aws.aws_account_health.logger")
def test_should_return_none_and_log_when_security_hub_lookup_fails(mock_logger):
    """A failed Security Hub lookup yields None (unavailable), not a clean count of 0, and is logged.

    Stub strategy: get_findings returns the UNAUTHORIZED classification the
    adapter gives InvalidAccessException (Security Hub not enabled).
    """
    # Arrange
    adapter = MagicMock(spec=SecurityHubAdapter)
    adapter.get_findings.return_value = _failure(error_code="InvalidAccessException")

    # Act
    result = aws_account_health.get_securityhub_summary(adapter, ACCOUNT_ID)

    # Assert
    assert result is None
    assert _logged_failure(mock_logger, "aws_health_securityhub_lookup_failed", "unauthorized")


@pytest.mark.unit
def test_should_get_ignored_security_hub_issues():
    """The root hardware-MFA controls are excluded from Security Hub findings by title."""
    # Act
    result = aws_account_health.get_ignored_security_hub_issues()

    # Assert
    assert result == [
        {"Value": "IAM.6 Hardware MFA should be enabled for the root user", "Comparison": "NOT_EQUALS"},
        {"Value": '1.14 Ensure hardware MFA is enabled for the "root" account', "Comparison": "NOT_EQUALS"},
    ]


# -- health_view_handler --------------------------------------------------------


@pytest.mark.unit
@patch("modules.aws.aws_account_health.get_account_health")
def test_should_render_health_modal_from_health_data(mock_get_health, view_body, slack_client):
    """A complete health check replaces the loading modal with cost amounts and ✅/❌ security lines.

    Stub strategy: get_account_health is patched with fully successful data so
    the test covers rendering only; lookups are covered by the helper tests.
    """
    # Arrange
    mock_get_health.return_value = _health()
    ack = MagicMock()

    # Act
    aws_account_health.health_view_handler(ack, view_body, slack_client)

    # Assert
    ack.assert_called_once_with()
    mock_get_health.assert_called_once_with(ACCOUNT_ID)
    slack_client.views_update.assert_called_once()
    assert slack_client.views_update.call_args.kwargs["view_id"] == "view-123"
    text = _view_text(slack_client.views_update.call_args.kwargs["view"])
    assert "2024-11-01 - 2024-11-30: $1,234.56 USD" in text
    assert "2024-12-01 - 2024-12-31: $5.00 USD" in text
    assert "✅ Config (0 issues)" in text
    assert "❌ GuardDuty (3 issues)" in text
    assert "✅ SecurityHub (0 issues)" in text
    assert "⚠️" not in text


@pytest.mark.unit
@patch("modules.aws.aws_account_health.get_account_health")
def test_should_render_per_field_warnings_for_unavailable_and_not_enabled(mock_get_health, view_body, slack_client):
    """Unavailable fields show ⚠️ unavailable and a disabled GuardDuty shows ⚠️ not enabled; other lines render normally.

    Stub strategy: health data mixes a failed cost month, a failed Security Hub
    lookup, GuardDuty not enabled and a Config count, so each rendering branch
    is visible in one modal and none of them reads as a clean ✅.
    """
    # Arrange
    mock_get_health.return_value = _health(last_amount=None, config=2, guardduty="not_enabled", securityhub=None)

    # Act
    aws_account_health.health_view_handler(MagicMock(), view_body, slack_client)

    # Assert
    text = _view_text(slack_client.views_update.call_args.kwargs["view"])
    assert "2024-11-01 - 2024-11-30: ⚠️ unavailable" in text
    assert "2024-12-01 - 2024-12-31: $5.00 USD" in text
    assert "❌ Config (2 issues)" in text
    assert "⚠️ GuardDuty (not enabled)" in text
    assert "⚠️ SecurityHub (unavailable)" in text
    assert "None" not in text
    assert "✅" not in text


@pytest.mark.unit
@pytest.mark.parametrize("error", [_client_error(), BotoCoreError()], ids=["client-error", "botocore-error"])
@patch("modules.aws.aws_account_health.logger")
@patch("modules.aws.aws_account_health.get_account_health")
def test_should_replace_loading_modal_with_error_when_health_check_raises_aws_error(
    mock_get_health, mock_logger, error, view_body, slack_client
):
    """An AWS error raised during the check (role assumption, unmapped code) replaces the loading modal with a bilingual error.

    Stub strategy: get_account_health raises the botocore exception. Updating
    the already-open view is what stops the modal from spinning on
    "Loading data..." forever; the log keeps the account for triage.
    """
    # Arrange
    mock_get_health.side_effect = error

    # Act
    aws_account_health.health_view_handler(MagicMock(), view_body, slack_client)

    # Assert
    slack_client.views_update.assert_called_once()
    assert slack_client.views_update.call_args.kwargs["view_id"] == "view-123"
    view = slack_client.views_update.call_args.kwargs["view"]
    assert "submit" not in view
    assert "close" in view
    text = _view_text(view)
    assert ENGLISH_RETRY in text
    assert FRENCH_RETRY in text
    assert any(kwargs.get("account_id") == ACCOUNT_ID for kwargs in _logged(mock_logger, "aws_health_check_failed"))


@pytest.mark.unit
@patch("modules.aws.aws_account_health.get_account_health")
def test_should_propagate_non_aws_errors_from_health_check(mock_get_health, view_body, slack_client):
    """Programmer errors are not swallowed by the AWS error handling.

    Stub strategy: get_account_health raises KeyError; the modal is not updated.
    """
    # Arrange
    mock_get_health.side_effect = KeyError("Groups")

    # Act / Assert
    with pytest.raises(KeyError):
        aws_account_health.health_view_handler(MagicMock(), view_body, slack_client)
    slack_client.views_update.assert_not_called()


# -- request_health_modal -------------------------------------------------------


@pytest.mark.unit
@patch("modules.aws.aws_account_health.build_organizations_adapter")
def test_should_open_account_selector_sorted_by_name(mock_build_organizations, slack_client):
    """The account selector lists every organization account, sorted case-insensitively by label.

    Stub strategy: a spec'd Organizations adapter returns two accounts out of order.
    """
    # Arrange
    adapter = MagicMock(spec=OrganizationsAdapter)
    adapter.list_organization_accounts.return_value = OperationResult.success(
        data=[{"Id": "222", "Name": "zebra"}, {"Id": "111", "Name": "Alpha"}]
    )
    mock_build_organizations.return_value = adapter

    # Act
    aws_account_health.request_health_modal(slack_client, {"trigger_id": "trigger-123"})

    # Assert
    mock_build_organizations.assert_called_once_with()
    slack_client.views_open.assert_called_once()
    call = slack_client.views_open.call_args
    assert call.kwargs["trigger_id"] == "trigger-123"
    view = call.kwargs["view"]
    assert view["callback_id"] == "aws_health_view"
    assert "submit" in view
    assert view["blocks"][0]["element"]["options"] == [
        {"text": {"type": "plain_text", "text": "Alpha (111)"}, "value": "111"},
        {"text": {"type": "plain_text", "text": "zebra (222)"}, "value": "222"},
    ]


@pytest.mark.unit
@patch("modules.aws.aws_account_health.logger")
@patch("modules.aws.aws_account_health.build_organizations_adapter")
def test_should_open_error_modal_when_account_list_fails(mock_build_organizations, mock_logger, slack_client):
    """A failed account listing opens a bilingual error modal with no submit button and logs the classification.

    Stub strategy: list_organization_accounts returns a classified UNAUTHORIZED
    failure, which previously crashed the options comprehension.
    """
    # Arrange
    adapter = MagicMock(spec=OrganizationsAdapter)
    adapter.list_organization_accounts.return_value = _failure()
    mock_build_organizations.return_value = adapter

    # Act
    aws_account_health.request_health_modal(slack_client, {"trigger_id": "trigger-123"})

    # Assert
    slack_client.views_open.assert_called_once()
    call = slack_client.views_open.call_args
    assert call.kwargs["trigger_id"] == "trigger-123"
    view = call.kwargs["view"]
    assert "submit" not in view
    assert "close" in view
    text = _view_text(view)
    assert ENGLISH_RETRY in text
    assert FRENCH_RETRY in text
    assert _logged_failure(mock_logger, "aws_health_accounts_list_failed", "unauthorized")


@pytest.mark.unit
@pytest.mark.parametrize("error", [_client_error(), BotoCoreError()], ids=["client-error", "botocore-error"])
@patch("modules.aws.aws_account_health.logger")
@patch("modules.aws.aws_account_health.build_organizations_adapter")
def test_should_open_error_modal_when_organizations_adapter_raises_aws_error(
    mock_build_organizations, mock_logger, error, slack_client
):
    """An AWS error raised while building the Organizations adapter opens the bilingual error modal and is logged.

    Stub strategy: the factory raises the botocore exception an eager AssumeRole
    failure produces, so /aws health never fails silently.
    """
    # Arrange
    mock_build_organizations.side_effect = error

    # Act
    aws_account_health.request_health_modal(slack_client, {"trigger_id": "trigger-123"})

    # Assert
    slack_client.views_open.assert_called_once()
    view = slack_client.views_open.call_args.kwargs["view"]
    assert "submit" not in view
    text = _view_text(view)
    assert ENGLISH_RETRY in text
    assert FRENCH_RETRY in text
    assert _logged(mock_logger, "aws_health_accounts_list_failed")
