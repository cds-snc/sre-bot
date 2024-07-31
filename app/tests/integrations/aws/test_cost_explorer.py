from unittest.mock import patch
from integrations.aws import cost_explorer


@patch("integrations.aws.cost_explorer.ORG_ROLE_ARN", "foo")
@patch("integrations.aws.cost_explorer.execute_aws_api_call")
def test_get_cost_and_usage_returns_cost_and_usage_list_when_success(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = [
        {"CostAndUsage": "foo"},
        {"CostAndUsage": "bar"},
    ]
    assert len(cost_explorer.get_cost_and_usage("foo", "bar", ["foo"])) == 2
    assert mock_execute_aws_api_call.called_with(
        "ce",
        "get_cost_and_usage",
        paginated=True,
        role_arn="foo",
        convert_kwargs=False,
        TimePeriod="foo",
        Granularity="bar",
        Metrics=["foo"],
    )


@patch("integrations.aws.cost_explorer.ORG_ROLE_ARN", "foo")
@patch("integrations.aws.cost_explorer.execute_aws_api_call")
def test_get_cost_and_usage_adds_filters_and_group_by_if_provided(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = [{"CostAndUsage": "foo"}]
    assert (
        len(
            cost_explorer.get_cost_and_usage(
                "foo",
                "bar",
                ["foo"],
                filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon S3"]}},
                group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )
        )
        == 1
    )
    assert mock_execute_aws_api_call.called_with(
        "ce",
        "get_cost_and_usage",
        paginated=True,
        role_arn="foo",
        convert_kwargs=False,
        TimePeriod="foo",
        Granularity="bar",
        Metrics=["foo"],
        Filter={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon S3"]}},
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
