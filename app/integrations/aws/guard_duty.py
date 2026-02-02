"""AWS GuardDuty integration module."""

import structlog
from core.config import settings
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

logger = structlog.get_logger()
LOGGING_ROLE_ARN = settings.aws.LOGGING_ROLE_ARN


@handle_aws_api_errors
def list_detectors():
    """Retrieves all detectors from AWS GuardDuty

    Returns:
        list: A list of detector objects.
    """
    log = logger.bind(operation="list_detectors")
    log.debug("guard_duty_list_detectors_started")
    response = execute_aws_api_call(
        "guardduty",
        "list_detectors",
        paginated=True,
        keys=["DetectorIds"],
        role_arn=LOGGING_ROLE_ARN,
    )
    detector_count = len(response) if response else 0
    log.debug("guard_duty_list_detectors_completed", detector_count=detector_count)
    return response if response else []


@handle_aws_api_errors
def get_findings_statistics(detector_id, finding_criteria=None):
    """Retrieves the findings statistics for a given detector

    Args:
        detector_id (str): The ID of the detector.
        finding_criteria (dict, optional): The criteria to use to filter the findings

    Returns:
        dict: The findings statistics.
    """
    log = logger.bind(operation="get_findings_statistics", detector_id=detector_id)
    log.debug(
        "guard_duty_get_findings_statistics_started",
        criteria_present=finding_criteria is not None,
    )

    params = {
        "DetectorId": detector_id,
        "FindingStatisticTypes": ["COUNT_BY_SEVERITY"],
    }
    if finding_criteria:
        params["FindingCriteria"] = finding_criteria

    response = execute_aws_api_call(
        "guardduty",
        "get_findings_statistics",
        role_arn=LOGGING_ROLE_ARN,
        **params,
    )

    has_findings = bool(
        response.get("FindingStatistics", {}).get("CountBySeverity", {})
    )
    log.debug(
        "guard_duty_get_findings_statistics_completed",
        has_findings=has_findings,
    )

    return response if response else {}
