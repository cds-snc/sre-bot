import os
from integrations.aws.client import execute_aws_api_call, handle_aws_api_errors

LOGGING_ROLE_ARN = os.environ.get("AWS_LOGGING_ACCOUNT_ROLE_ARN")


@handle_aws_api_errors
def list_detectors():
    """Retrieves all detectors from AWS GuardDuty

    Returns:
        list: A list of detector objects.
    """
    response = execute_aws_api_call(
        "guardduty",
        "list_detectors",
        paginated=True,
        keys=["DetectorIds"],
        role_arn=LOGGING_ROLE_ARN,
    )
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

    return response if response else {}
