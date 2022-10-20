import arrow

from integrations import aws_account_health

from unittest.mock import call, MagicMock, patch


@patch("integrations.aws_account_health.boto3")
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


@patch("integrations.aws_account_health.assume_role_client")
def test_get_accounts(assume_role_client_mock):
    client = MagicMock()
    client.list_accounts.side_effect = [
        {
            "Accounts": [
                {
                    "Id": "test_account_id",
                    "Name": "test_account_name",
                }
            ],
            "NextToken": "test_next_token",
        },
        {
            "Accounts": [
                {
                    "Id": "test_account_id_2",
                    "Name": "test_account_name_2",
                }
            ],
        },
    ]
    assume_role_client_mock.return_value = client
    assert aws_account_health.get_accounts() == {
        "test_account_id": "test_account_name",
        "test_account_id_2": "test_account_name_2",
    }


@patch("integrations.aws_account_health.get_account_spend")
def test_get_account_health(get_account_spend_mock):
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

    assert result.get("account_id") == "test_account_id"
    assert "cost" in result
    assert "security" in result


@patch("integrations.aws_account_health.assume_role_client")
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


@patch("integrations.aws_account_health.assume_role_client")
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
