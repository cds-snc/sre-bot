from unittest.mock import patch
from integrations.aws import security_hub


@patch("integrations.aws.security_hub.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.security_hub.execute_aws_api_call")
def test_get_findings_returns_findings_list_when_success(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = [
        {"Findings": [{"Severity": {"Label": "LOW"}}], "NextToken": "foo"},
        {"Findings": [{"Severity": {"Label": "MEDIUM"}}]},
    ]
    assert len(security_hub.get_findings({})) == 2
    assert mock_execute_aws_api_call.called_with(
        "securityhub",
        "get_findings",
        paginated=True,
        role_arn="foo",
        filters={},
    )


@patch("integrations.aws.security_hub.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.security_hub.execute_aws_api_call")
def test_get_findings_returns_empty_findings_list(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = [{"Findings": []}]
    assert len(security_hub.get_findings({})) == 1
    assert mock_execute_aws_api_call.called_with(
        "securityhub",
        "get_findings",
        paginated=True,
        role_arn="foo",
        filters={},
    )


@patch("integrations.aws.security_hub.LOGGING_ROLE_ARN", "foo")
@patch("integrations.aws.security_hub.execute_aws_api_call")
def test_get_findings_returns_empty_findings_list_when_no_findings(
    mock_execute_aws_api_call,
):
    mock_execute_aws_api_call.return_value = []
    assert len(security_hub.get_findings({})) == 0
    assert mock_execute_aws_api_call.called_with(
        "securityhub",
        "get_findings",
        paginated=True,
        role_arn="foo",
        filters={},
    )
