"""Unit tests for AWS spending data handler."""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd

from modules.aws import spending


@pytest.mark.unit
@patch("modules.aws.spending.get_settings")
@patch("modules.aws.spending.organizations")
def test_should_generate_spending_data_successfully(
    mock_organizations, mock_get_settings
):
    """Test successful spending data generation."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.google_resources.spending_sheet_id = "test_sheet_id"
    mock_get_settings.return_value = mock_settings

    mock_organizations.list_organization_accounts.return_value = [
        {"Id": "123456789012", "Name": "TestAccount"}
    ]

    # Act - Test with actual spending data to avoid merge issues
    with patch("modules.aws.spending.get_accounts_details") as mock_get_details:
        with patch("modules.aws.spending.get_accounts_spending") as mock_get_spending:
            mock_get_details.return_value = [
                {
                    "Linked account": "123456789012",
                    "Linked account name": "TestAccount",
                    "Product": "TestProduct",
                    "Business Unit": "TestBU",
                }
            ]
            mock_get_spending.return_value = [
                {
                    "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-31"},
                    "Groups": [
                        {
                            "Keys": ["123456789012", "s3"],
                            "Metrics": {
                                "UnblendedCost": {
                                    "Amount": "100.00",
                                    "Unit": "USD",
                                }
                            },
                        }
                    ],
                }
            ]

            result = spending.generate_spending_data()

            # Assert
            assert isinstance(result, pd.DataFrame)
            assert len(result) > 0
            mock_get_details.assert_called_once()
            mock_get_spending.assert_called_once()


@pytest.mark.unit
def test_should_return_empty_dataframe_when_no_spending_data_provided():
    """Test handling of empty spending data."""
    # Arrange
    spending_data = []

    # Act
    result = spending.spending_to_df(spending_data)

    # Assert
    assert isinstance(result, pd.DataFrame)
    assert result.empty


@pytest.mark.unit
def test_should_flatten_spending_data_correctly():
    """Test correct flattening of spending data structure."""
    # Arrange
    spending_data = [
        {
            "TimePeriod": {"Start": "2024-01-01", "End": "2024-01-31"},
            "Groups": [
                {
                    "Keys": ["123456789012", "s3"],
                    "Metrics": {
                        "UnblendedCost": {
                            "Amount": "100.00",
                            "Unit": "USD",
                        }
                    },
                }
            ],
        }
    ]

    # Act
    result = spending.spending_to_df(spending_data)

    # Assert
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["Linked account"] == "123456789012"
    assert result.iloc[0]["Service"] == "s3"
    assert float(result.iloc[0]["Cost Amount"]) == 100.00
    assert result.iloc[0]["Period"] == "2024-01-01"


@pytest.mark.unit
@patch("modules.aws.spending.sheets")
@patch("modules.aws.spending.get_settings")
def test_should_update_spending_data_in_sheet(mock_get_settings, mock_sheets):
    """Test updating spending data in Google Sheets."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.google_resources.spending_sheet_id = "test_sheet_id"
    mock_get_settings.return_value = mock_settings

    data = {"Account": ["123456789012"], "Cost": [100.00]}
    df = pd.DataFrame(data)

    # Act
    spending.update_spending_data(df, spreadsheet_id="test_sheet_id")

    # Assert
    mock_sheets.batch_update_values.assert_called_once()
    call_kwargs = mock_sheets.batch_update_values.call_args[1]
    assert call_kwargs["spreadsheetId"] == "test_sheet_id"
    assert call_kwargs["cell_range"] == "Sheet1"
    assert call_kwargs["valueInputOption"] == "USER_ENTERED"


@pytest.mark.unit
@patch("modules.aws.spending.sheets")
def test_should_skip_update_when_spreadsheet_id_not_set(mock_sheets):
    """Test that update is skipped when spreadsheet ID is not set."""
    # Arrange
    data = {"Account": ["123456789012"], "Cost": [100.00]}
    df = pd.DataFrame(data)

    # Act
    spending.update_spending_data(df, spreadsheet_id=None)

    # Assert
    mock_sheets.batch_update_values.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.spending.get_settings")
@patch("modules.aws.spending.generate_spending_data")
@patch("modules.aws.spending.update_spending_data")
def test_should_execute_and_update_spending_job_successfully(
    mock_update, mock_generate, mock_get_settings
):
    """Test successful execution of spending data update job."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.google_resources.spending_sheet_id = "test_sheet_id"
    mock_get_settings.return_value = mock_settings

    mock_spending_data = pd.DataFrame({"Account": ["123456789012"], "Cost": [100.00]})
    mock_generate.return_value = mock_spending_data

    # Act
    spending.execute_spending_data_update_job()

    # Assert
    mock_generate.assert_called_once()
    mock_update.assert_called_once_with(mock_spending_data)


@pytest.mark.unit
@patch("modules.aws.spending.get_settings")
@patch("modules.aws.spending.generate_spending_data")
@patch("modules.aws.spending.update_spending_data")
def test_should_skip_update_when_spending_data_empty(
    mock_update, mock_generate, mock_get_settings
):
    """Test that update is skipped when spending data is empty."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.google_resources.spending_sheet_id = "test_sheet_id"
    mock_get_settings.return_value = mock_settings

    mock_spending_data = pd.DataFrame()
    mock_generate.return_value = mock_spending_data

    # Act
    spending.execute_spending_data_update_job()

    # Assert
    mock_generate.assert_called_once()
    mock_update.assert_not_called()
