import os
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

AUDIT_ROLE_ARN = os.environ.get("AWS_AUDIT_ACCOUNT_ROLE_ARN")


@handle_aws_api_errors
def describe_aggregate_compliance_by_config_rules(config_aggregator_name, filters):
    """Retrieves the aggregate compliance of AWS Config rules for an account.

    Args:
        config_aggregator_name (str): The name of the AWS Config aggregator.
        filters (dict): Filters to apply to the compliance results.

    Returns:
        list: A list of compliance objects
    """
    params = {
        "ConfigurationAggregatorName": config_aggregator_name,
        "Filters": filters,
    }
    response = execute_aws_api_call(
        "config",
        "describe_aggregate_compliance_by_config_rules",
        paginated=True,
        keys=["AggregateComplianceByConfigRules"],
        role_arn=AUDIT_ROLE_ARN,
        **params,
    )
    return response if response else []
