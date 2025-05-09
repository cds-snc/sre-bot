from unittest.mock import patch
from integrations.aws import cost_explorer


@patch("integrations.aws.cost_explorer.ORG_ROLE_ARN", "foo")
@patch("integrations.aws.cost_explorer.execute_aws_api_call")
def test_get_cost_and_usage_returns_cost_and_usage_list_when_success(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                "Total": {"UnblendedCost": {"Amount": "100", "Unit": "USD"}},
                "Estimated": False,
            },
            {
                "TimePeriod": {"Start": "2023-02-01", "End": "2023-02-28"},
                "Total": {"UnblendedCost": {"Amount": "200", "Unit": "USD"}},
                "Estimated": False,
            },
        ]
    }
    response = cost_explorer.get_cost_and_usage("foo", "bar", ["foo"])
    assert "ResultsByTime" in response
    assert len(response["ResultsByTime"]) == 2
    mock_execute_aws_api_call.assert_called_once_with(
        "ce",
        "get_cost_and_usage",
        role_arn="foo",
        TimePeriod="foo",
        Granularity="bar",
        Metrics=["foo"],
    )


@patch("integrations.aws.cost_explorer.ORG_ROLE_ARN", "foo")
@patch("integrations.aws.cost_explorer.execute_aws_api_call")
def test_get_cost_and_usage_adds_filters_and_group_by_if_provided(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                "Total": {"UnblendedCost": {"Amount": "100", "Unit": "USD"}},
                "Groups": [
                    {
                        "Keys": ["Amazon S3"],
                        "Metrics": {"UnblendedCost": {"Amount": "50", "Unit": "USD"}},
                    }
                ],
                "Estimated": False,
            }
        ]
    }
    response = cost_explorer.get_cost_and_usage(
        "foo",
        "bar",
        ["foo"],
        filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon S3"]}},
        group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    assert "ResultsByTime" in response
    assert len(response["ResultsByTime"]) == 1
    mock_execute_aws_api_call.assert_called_once_with(
        "ce",
        "get_cost_and_usage",
        role_arn="foo",
        TimePeriod="foo",
        Granularity="bar",
        Metrics=["foo"],
        Filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon S3"]}},
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
