from unittest.mock import patch
from integrations.aws import guard_duty


@patch("integrations.aws.guard_duty.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.guard_duty.execute_aws_api_call")
def test_list_detectors_returns_list_when_success(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["foo", "bar"]
    assert len(guard_duty.list_detectors()) == 2
    mock_execute_aws_api_call.assert_called_once_with(
        "guardduty",
        "list_detectors",
        paginated=True,
        keys=["DetectorIds"],
        role_arn="foo",
    )


@patch("integrations.aws.guard_duty.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.guard_duty.execute_aws_api_call")
def test_list_detectors_returns_empty_list_when_no_detectors(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = []
    assert len(guard_duty.list_detectors()) == 0
    mock_execute_aws_api_call.assert_called_once_with(
        "guardduty",
        "list_detectors",
        paginated=True,
        keys=["DetectorIds"],
        role_arn="foo",
    )


@patch("integrations.aws.guard_duty.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.guard_duty.execute_aws_api_call")
def test_get_findings_statistics_returns_statistics_when_success(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = {
        "FindingStatistics": {
            "CountBySeverity": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        }
    }
    assert guard_duty.get_findings_statistics("test_detector_id") == {
        "FindingStatistics": {
            "CountBySeverity": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        }
    }
    mock_execute_aws_api_call.assert_called_once_with(
        "guardduty",
        "get_findings_statistics",
        role_arn="foo",
        DetectorId="test_detector_id",
        FindingStatisticTypes=["COUNT_BY_SEVERITY"],
    )


@patch("integrations.aws.guard_duty.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.guard_duty.execute_aws_api_call")
def test_get_findings_statistics_returns_empty_object_if_no_statistics_found(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = {}
    assert guard_duty.get_findings_statistics("test_detector_id") == {}
    mock_execute_aws_api_call.assert_called_once_with(
        "guardduty",
        "get_findings_statistics",
        role_arn="foo",
        DetectorId="test_detector_id",
        FindingStatisticTypes=["COUNT_BY_SEVERITY"],
    )


@patch("integrations.aws.guard_duty.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.guard_duty.execute_aws_api_call")
def test_get_findings_statistics_parse_finding_criteria(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = {
        "FindingStatistics": {
            "CountBySeverity": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        }
    }
    assert guard_duty.get_findings_statistics(
        "test_detector_id", finding_criteria={"Criterion": {"foo": "bar"}}
    ) == {
        "FindingStatistics": {
            "CountBySeverity": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        }
    }
    mock_execute_aws_api_call.assert_called_once_with(
        "guardduty",
        "get_findings_statistics",
        role_arn="foo",
        DetectorId="test_detector_id",
        FindingStatisticTypes=["COUNT_BY_SEVERITY"],
        FindingCriteria={"Criterion": {"foo": "bar"}},
    )
