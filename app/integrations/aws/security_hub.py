import os
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

LOGGING_ROLE_ARN = os.environ.get("AWS_LOGGING_ACCOUNT_ROLE_ARN")


@handle_aws_api_errors
def get_findings(filters):
    """Retrieves all findings from AWS Security Hub

    Args:
        filters (dict): Filters to apply to the findings.

    Returns:
        list: A list of finding objects.
    """
    response = execute_aws_api_call(
        "securityhub",
        "get_findings",
        paginated=True,
        role_arn=LOGGING_ROLE_ARN,
        Filters=filters,
    )
    return response
