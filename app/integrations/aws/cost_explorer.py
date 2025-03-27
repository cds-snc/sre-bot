"""Cost Explorer API integration."""

from core.config import settings
from core.logging import get_module_logger
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = get_module_logger()
ORG_ROLE_ARN = settings.aws.ORG_ROLE_ARN


@handle_aws_api_errors
def get_cost_and_usage(time_period, granularity, metrics, filter=None, group_by=None):
    logger.debug(
        "cost_explorer_get_cost_and_usage_started",
        granularity=granularity,
        metrics=metrics,
        filter_present=filter is not None,
        group_by_present=group_by is not None,
    )

    params = {
        "TimePeriod": time_period,
        "Granularity": granularity,
        "Metrics": metrics,
    }
    if filter:
        params["Filter"] = filter
    if group_by:
        params["GroupBy"] = group_by

    response = execute_aws_api_call(
        "ce",
        "get_cost_and_usage",
        role_arn=ORG_ROLE_ARN,
        **params,
    )

    result_size = len(response.get("ResultsByTime", [])) if response else 0
    logger.debug("cost_explorer_get_cost_and_usage_completed", result_count=result_size)

    return response
