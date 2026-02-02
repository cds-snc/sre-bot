"""Cost Explorer API integration."""

import structlog
from core.config import settings
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = structlog.get_logger()
ORG_ROLE_ARN = settings.aws.ORG_ROLE_ARN


@handle_aws_api_errors
def get_cost_and_usage(time_period, granularity, metrics, filter=None, group_by=None):
    log = logger.bind(
        operation="get_cost_and_usage", granularity=granularity, metrics=str(metrics)
    )
    log.debug(
        "cost_explorer_get_cost_and_usage_started",
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
    log.debug("cost_explorer_get_cost_and_usage_completed", result_count=result_size)

    return response
