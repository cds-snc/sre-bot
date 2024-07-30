import arrow
import os

from modules.aws import aws_account_health

from unittest.mock import ANY, call, MagicMock, patch


@patch("modules.aws.aws_account_health.boto3")
def test_assume_role_client_returns_session(boto3_mock):
    client = MagicMock()
    client.assume_role.return_value = {
        "Credentials": {
            "AccessKeyId": "test_access_key_id",
            "SecretAccessKey": "test_secret_access_key",
            "SessionToken": "test_session_token",
        }
    }
    session = MagicMock()
    session.client.return_value = "session-client"
    boto3_mock.client.return_value = client
    boto3_mock.Session.return_value = session
    assert aws_account_health.assume_role_client("identitystore") == "session-client"
    assert boto3_mock.client.call_count == 1
    assert boto3_mock.Session.call_count == 1
    assert boto3_mock.Session.call_args == call(
        aws_access_key_id="test_access_key_id",
        aws_secret_access_key="test_secret_access_key",
        aws_session_token="test_session_token",
    )


@patch("modules.aws.aws_account_health.get_securityhub_summary")
@patch("modules.aws.aws_account_health.get_guardduty_summary")
@patch("modules.aws.aws_account_health.get_config_summary")
@patch("modules.aws.aws_account_health.get_account_spend")
def test_get_account_health(
    get_account_spend_mock,
    get_config_summary_mock,
    get_guardduty_summary_mock,
    get_securityhub_summary_mock,
):
    last_day_of_current_month = arrow.utcnow().span("month")[1].format("YYYY-MM-DD")
    first_day_of_current_month = arrow.utcnow().span("month")[0].format("YYYY-MM-DD")
    last_day_of_last_month = (
        arrow.utcnow().shift(months=-1).span("month")[1].format("YYYY-MM-DD")
    )
    first_day_of_last_month = (
        arrow.utcnow().shift(months=-1).span("month")[0].format("YYYY-MM-DD")
    )

    result = aws_account_health.get_account_health("test_account_id")

    assert get_account_spend_mock.called_with(
        "test_account_id", first_day_of_current_month, last_day_of_current_month
    )
    assert get_account_spend_mock.called_with(
        "test_account_id", first_day_of_last_month, last_day_of_last_month
    )

    assert get_config_summary_mock.called_with("test_account_id")
    assert get_guardduty_summary_mock.called_with("test_account_id")
    assert get_securityhub_summary_mock.called_with("test_account_id")

    assert result.get("account_id") == "test_account_id"
    assert "cost" in result
    assert "security" in result


@patch("modules.aws.aws_account_health.assume_role_client")
def test_get_account_spend_with_data(assume_role_client_mock):
    client = MagicMock()
    client.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {"Groups": [{"Metrics": {"UnblendedCost": {"Amount": "100.123456789"}}}]}
        ]
    }
    assume_role_client_mock.return_value = client
    assert (
        aws_account_health.get_account_spend(
            "test_account_id", "2020-01-01", "2020-01-31"
        )
        == "100.12"
    )
    assert client.get_cost_and_usage.called_with(
        TimePeriod={"Start": "2020-01-01", "End": "2020-01-31"},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        Filter={"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": ["test_account_id"]}},
    )


@patch("modules.aws.aws_account_health.assume_role_client")
def test_get_account_spend_with_no_data(assume_role_client_mock):
    client = MagicMock()
    client.get_cost_and_usage.return_value = {"ResultsByTime": [{}]}
    assume_role_client_mock.return_value = client
    assert (
        aws_account_health.get_account_spend(
            "test_account_id", "2020-01-01", "2020-01-31"
        )
        == "0.00"
    )
    assert client.get_cost_and_usage.called_with(
        TimePeriod={"Start": "2020-01-01", "End": "2020-01-31"},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        Filter={"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": ["test_account_id"]}},
    )


@patch("modules.aws.aws_account_health.assume_role_client")
def test_get_config_summary(assume_role_client_mock):
    client = MagicMock()
    client.describe_aggregate_compliance_by_config_rules.return_value = {
        "AggregateComplianceByConfigRules": ["foo"]
    }
    assume_role_client_mock.return_value = client
    assert aws_account_health.get_config_summary("test_account_id") == 1
    assert assume_role_client_mock.called_with(
        "config", role=os.environ["AWS_AUDIT_ACCOUNT_ROLE_ARN"]
    )


@patch("modules.aws.aws_account_health.assume_role_client")
def test_get_guardduty_summary(assume_role_client_mock):
    client = MagicMock()
    client.list_detectors.return_value = {"DetectorIds": ["foo"]}
    client.get_findings_statistics.return_value = {
        "FindingStatistics": {"CountBySeverity": {"foo": 1}}
    }
    assume_role_client_mock.return_value = client
    assert aws_account_health.get_guardduty_summary("test_account_id") == 1
    assert assume_role_client_mock.called_with(
        "guardduty", role=os.environ["AWS_LOGGING_ACCOUNT_ROLE_ARN"]
    )


@patch("modules.aws.aws_account_health.assume_role_client")
def test_get_securityhub_summary(assume_role_client_mock):
    client = MagicMock()
    client.get_findings.side_effect = [
        {"Findings": [{"Severity": {"Label": "LOW"}}], "NextToken": "foo"},
        {"Findings": [{"Severity": {"Label": "MEDIUM"}}]},
    ]
    assume_role_client_mock.return_value = client
    assert aws_account_health.get_securityhub_summary("test_account_id") == 2
    assert assume_role_client_mock.called_with(
        "securityhub", role=os.environ["AWS_LOGGING_ACCOUNT_ROLE_ARN"]
    )


def test_get_ignored_security_hub_issues():
    assert aws_account_health.get_ignored_security_hub_issues() == [
        {
            "Comparison": "NOT_EQUALS",
            "Value": "IAM.6 Hardware MFA should be enabled for the root user",
        },
        {
            "Comparison": "NOT_EQUALS",
            "Value": '1.14 Ensure hardware MFA is enabled for the "root" account',
        },
    ]


@patch("modules.aws.aws_account_health.get_account_health")
def test_health_view_handler(get_account_health_mock):
    ack = MagicMock()
    body = {
        "trigger_id": "trigger_id",
        "view": {
            "state": {
                "values": {
                    "account": {
                        "account": {
                            "selected_option": {
                                "value": "account_id",
                                "text": {"text": "account_name"},
                            }
                        }
                    }
                }
            }
        },
    }
    client = MagicMock()

    aws_account_health.health_view_handler(ack, body, MagicMock(), client)
    ack.assert_called
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
    )


@patch("modules.aws.aws.aws_account_health.organizations.list_organization_accounts")
def test_request_health_modal(get_accounts_mocks):
    client = MagicMock()
    body = {"trigger_id": "trigger_id", "view": {"state": {"values": {}}}}

    get_accounts_mocks.return_value = [{"Id": "id", "Name": "name"}]

    aws_account_health.request_health_modal(client, body)
    client.views_open.assert_called_with(
        trigger_id="trigger_id",
        view=ANY,
    )
