import structlog
from core.config import settings
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = structlog.get_logger()
LOGGING_ROLE_ARN = settings.aws.LOGGING_ROLE_ARN


@handle_aws_api_errors
def get_findings(filters):
    """Retrieves all findings from AWS Security Hub

    Args:
        filters (dict): Filters to apply to the findings.

    Returns:
        list: A list of finding objects.
    """
    log = logger.bind(operation="get_findings", filter_keys=list(filters.keys()))
    log.debug("security_hub_get_findings_started")
    response = execute_aws_api_call(
        "securityhub",
        "get_findings",
        paginated=True,
        role_arn=LOGGING_ROLE_ARN,
        Filters=filters,
    )
    finding_count = len(response) if response else 0
    log.debug("security_hub_get_findings_completed", finding_count=finding_count)
    return response
