"""Unit tests for AWS account health handler."""

import pytest
from unittest.mock import MagicMock, patch

from modules.aws import aws_account_health


@pytest.mark.unit
@patch("modules.aws.aws_account_health.get_guardduty_summary")
@patch("modules.aws.aws_account_health.get_config_summary")
@patch("modules.aws.aws_account_health.get_account_spend")
@patch("modules.aws.aws_account_health.get_securityhub_summary")
def test_should_get_account_health_successfully(
    mock_securityhub,
    mock_spend,
    mock_config,
    mock_guardduty,
):
    """Test get_account_health returns complete health data."""
    # Arrange
    mock_spend.return_value = "100.00"
    mock_config.return_value = 2
    mock_guardduty.return_value = 1
    mock_securityhub.return_value = 5

    # Act
    result = aws_account_health.get_account_health("account-123")

    # Assert
    assert result["account_id"] == "account-123"
    assert "cost" in result
    assert "security" in result
    assert result["cost"]["last_month"]["amount"] == "100.00"
    assert result["security"]["config"] == 2
    assert result["security"]["guardduty"] == 1
    assert result["security"]["securityhub"] == 5


@pytest.mark.unit
@patch("modules.aws.aws_account_health.cost_explorer")
def test_should_get_account_spend_with_data(mock_cost_explorer):
    """Test get_account_spend returns formatted cost when data available."""
    # Arrange
    mock_cost_explorer.get_cost_and_usage.return_value = {
        "ResultsByTime": [
            {"Groups": [{"Metrics": {"UnblendedCost": {"Amount": "123.456789"}}}]}
        ]
    }

    # Act
    result = aws_account_health.get_account_spend(
        "account-123", "2024-01-01", "2024-01-31"
    )

    # Assert
    assert result == "123.46"


@pytest.mark.unit
@patch("modules.aws.aws_account_health.cost_explorer")
def test_should_return_zero_when_no_spend_data(mock_cost_explorer):
    """Test get_account_spend returns 0.00 when no data available."""
    # Arrange
    mock_cost_explorer.get_cost_and_usage.return_value = {"ResultsByTime": [{}]}

    # Act
    result = aws_account_health.get_account_spend(
        "account-123", "2024-01-01", "2024-01-31"
    )

    # Assert
    assert result == "0.00"


@pytest.mark.unit
@patch("modules.aws.aws_account_health.cost_explorer")
def test_should_return_zero_when_no_groups_in_spend_data(mock_cost_explorer):
    """Test get_account_spend returns 0.00 when Groups is empty."""
    # Arrange
    mock_cost_explorer.get_cost_and_usage.return_value = {
        "ResultsByTime": [{"Groups": []}]
    }

    # Act
    result = aws_account_health.get_account_spend(
        "account-123", "2024-01-01", "2024-01-31"
    )

    # Assert
    assert result == "0.00"


@pytest.mark.unit
@patch("modules.aws.aws_account_health.config")
def test_should_get_config_summary_successfully(mock_config):
    """Test get_config_summary returns compliance count."""
    # Arrange
    mock_config.describe_aggregate_compliance_by_config_rules.return_value = [
        {"ConfigRuleName": "rule-1"},
        {"ConfigRuleName": "rule-2"},
    ]

    # Act
    result = aws_account_health.get_config_summary("account-123")

    # Assert
    assert result == 2
    mock_config.describe_aggregate_compliance_by_config_rules.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.aws_account_health.config")
def test_should_return_zero_when_no_config_issues(mock_config):
    """Test get_config_summary returns 0 when no compliance issues."""
    # Arrange
    mock_config.describe_aggregate_compliance_by_config_rules.return_value = []

    # Act
    result = aws_account_health.get_config_summary("account-123")

    # Assert
    assert result == 0


@pytest.mark.unit
@patch("modules.aws.aws_account_health.guard_duty")
def test_should_get_guardduty_summary_successfully(mock_guard_duty):
    """Test get_guardduty_summary returns finding count."""
    # Arrange
    mock_guard_duty.list_detectors.return_value = ["detector-123"]
    mock_guard_duty.get_findings_statistics.return_value = {
        "FindingStatistics": {
            "CountBySeverity": {
                "LOW": 0,
                "MEDIUM": 1,
                "HIGH": 2,
            }
        }
    }

    # Act
    result = aws_account_health.get_guardduty_summary("account-123")

    # Assert
    assert result == 3


@pytest.mark.unit
@patch("modules.aws.aws_account_health.guard_duty")
def test_should_return_zero_guardduty_when_no_findings(mock_guard_duty):
    """Test get_guardduty_summary returns 0 when no findings."""
    # Arrange
    mock_guard_duty.list_detectors.return_value = ["detector-123"]
    mock_guard_duty.get_findings_statistics.return_value = {
        "FindingStatistics": {"CountBySeverity": {}}
    }

    # Act
    result = aws_account_health.get_guardduty_summary("account-123")

    # Assert
    assert result == 0


@pytest.mark.unit
@patch("modules.aws.aws_account_health.get_ignored_security_hub_issues")
@patch("modules.aws.aws_account_health.security_hub")
def test_should_get_securityhub_summary_successfully(
    mock_security_hub, mock_get_ignored
):
    """Test get_securityhub_summary returns finding count."""
    # Arrange
    mock_get_ignored.return_value = []
    mock_security_hub.get_findings.return_value = [
        {
            "Findings": [
                {"Id": "finding-1"},
                {"Id": "finding-2"},
            ]
        }
    ]

    # Act
    result = aws_account_health.get_securityhub_summary("account-123")

    # Assert
    assert result == 2


@pytest.mark.unit
@patch("modules.aws.aws_account_health.get_ignored_security_hub_issues")
@patch("modules.aws.aws_account_health.security_hub")
def test_should_return_zero_securityhub_when_no_findings(
    mock_security_hub, mock_get_ignored
):
    """Test get_securityhub_summary returns 0 when no findings."""
    # Arrange
    mock_get_ignored.return_value = []
    mock_security_hub.get_findings.return_value = []

    # Act
    result = aws_account_health.get_securityhub_summary("account-123")

    # Assert
    assert result == 0


@pytest.mark.unit
def test_should_get_ignored_security_hub_issues():
    """Test get_ignored_security_hub_issues returns expected filters."""
    # Act
    result = aws_account_health.get_ignored_security_hub_issues()

    # Assert
    assert isinstance(result, list)
    assert len(result) == 2
    assert any("MFA" in str(issue) for issue in result)


@pytest.mark.unit
@patch("modules.aws.aws_account_health.get_account_health")
def test_should_handle_health_view_handler(mock_get_health):
    """Test health_view_handler processes account health request."""
    # Arrange
    mock_get_health.return_value = {
        "account_id": "account-123",
        "cost": {
            "last_month": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "amount": "100.00",
            },
            "current_month": {
                "start_date": "2024-02-01",
                "end_date": "2024-02-29",
                "amount": "75.00",
            },
        },
        "security": {"config": 0, "guardduty": 0, "securityhub": 0},
    }
    ack = MagicMock()
    body = {
        "view": {
            "state": {
                "values": {
                    "account": {
                        "account": {
                            "selected_option": {
                                "value": "account-123",
                                "text": {"text": "TestAccount (account-123)"},
                            }
                        }
                    }
                }
            }
        },
        "trigger_id": "trigger-123",
    }
    client = MagicMock()
    client.views_open.return_value = {"view": {"id": "view-123"}}

    # Act
    aws_account_health.health_view_handler(ack, body, client)

    # Assert
    ack.assert_called_once()
    mock_get_health.assert_called_once_with("account-123")
    client.views_open.assert_called_once()
    client.views_update.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.aws_account_health.organizations")
def test_should_request_health_modal(mock_organizations):
    """Test request_health_modal fetches and displays accounts."""
    # Arrange
    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "account-1", "Name": "Account1"},
        {"Id": "account-2", "Name": "Account2"},
    ]
    client = MagicMock()
    body = MagicMock()

    # Act
    aws_account_health.request_health_modal(client, body)

    # Assert
    mock_organizations.list_organization_accounts.assert_called_once()
    client.views_open.assert_called_once()
