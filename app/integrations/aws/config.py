import structlog

from core.config import settings
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = structlog.get_logger()
AUDIT_ROLE_ARN = settings.aws.AUDIT_ROLE_ARN


@handle_aws_api_errors
def describe_aggregate_compliance_by_config_rules(config_aggregator_name, filters):
    """Retrieves the aggregate compliance of AWS Config rules for an account.

    Args:
        config_aggregator_name (str): The name of the AWS Config aggregator.
        filters (dict): Filters to apply to the compliance results.

    Returns:
        list: A list of compliance objects
    """
    log = logger.bind(
        operation="describe_aggregate_compliance_by_config_rules",
        aggregator=config_aggregator_name,
        filter_keys=list(filters.keys()) if filters else [],
    )
    log.debug("config_describe_aggregate_compliance_started")

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

    rule_count = len(response) if response else 0
    log.debug("config_describe_aggregate_compliance_completed", rule_count=rule_count)

    return response if response else []
