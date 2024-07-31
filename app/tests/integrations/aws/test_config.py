from unittest.mock import patch
from integrations.aws import config


@patch("integrations.aws.config.AUDIT_ROLE_ARN", "foo")
@patch("integrations.aws.config.execute_aws_api_call")
def test_describe_aggregate_compliance_by_config_rules_returns_compliance_list_when_success(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = [{"config": "foo"}, {"config": "bar"}]
    assert len(config.describe_aggregate_compliance_by_config_rules("foo", {})) == 2
    assert mock_execute_aws_api_call.called_with(
        "config",
        "describe_aggregate_compliance_by_config_rules",
        paginated=True,
        keys=["AggregateComplianceByConfigRules"],
        role_arn="foo",
        convert_kwargs=False,
        ConfigurationAggregatorName="foo",
        Filters={},
    )


@patch("integrations.aws.config.AUDIT_ROLE_ARN", "foo")
@patch("integrations.aws.config.execute_aws_api_call")
def test_describe_aggregate_compliance_by_config_rules_returns_empty_compliance_list(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = []
    assert len(config.describe_aggregate_compliance_by_config_rules("foo", {})) == 0
    assert mock_execute_aws_api_call.called_with(
        "config",
        "describe_aggregate_compliance_by_config_rules",
        paginated=True,
        keys=["AggregateComplianceByConfigRules"],
        role_arn="foo",
        convert_kwargs=False,
        ConfigurationAggregatorName="foo",
        Filters={},
    )


@patch("integrations.aws.config.AUDIT_ROLE_ARN", "foo")
@patch("integrations.aws.config.execute_aws_api_call")
def test_describe_aggregate_compliance_by_config_rules_passes_filters_to_api_call(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = [{"config": "foo"}]
    assert len(
        config.describe_aggregate_compliance_by_config_rules(
            "foo", {"AccountId": "123456789012"}
        )
    ) == 1
    assert mock_execute_aws_api_call.called_with(
        "config",
        "describe_aggregate_compliance_by_config_rules",
        paginated=True,
        keys=["AggregateComplianceByConfigRules"],
        role_arn="foo",
        convert_kwargs=False,
        ConfigurationAggregatorName="foo",
        Filters={"AccountId": "123456789012"},
    )
