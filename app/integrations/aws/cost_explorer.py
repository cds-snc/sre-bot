"""Cost Explorer API integration."""
import os
from .client import execute_aws_api_call, handle_aws_api_errors

ORG_ROLE_ARN = os.environ.get("AWS_ORG_ACCOUNT_ROLE_ARN")


@handle_aws_api_errors
def get_cost_and_usage(time_period, granularity, metrics, filter=None, group_by=None):
    params = {
        "TimePeriod": time_period,
        "Granularity": granularity,
        "Metrics": metrics,
    }
    if filter:
        params["Filter"] = filter
    if group_by:
        params["GroupBy"] = group_by

    return execute_aws_api_call(
        "ce",
        "get_cost_and_usage",
        role_arn=ORG_ROLE_ARN,
        convert_kwargs=False,
        **params,
    )
