"""Unit tests for the AWS spending module."""

from unittest.mock import patch, MagicMock, call
import pandas as pd

from modules.aws import spending


@patch("modules.aws.spending.get_accounts_details")
@patch("modules.aws.spending.get_accounts_spending")
@patch("modules.aws.spending.spending_to_df")
@patch("modules.aws.spending.organizations.list_organization_accounts")
@patch("modules.aws.spending.pd.merge")
def test_generate_spending_data(
    mock_merge,
    mock_list_accounts,
    mock_spending_to_df,
    mock_get_spending,
    mock_get_details,
):
    """Test the generate_spending_data function."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_list_accounts.return_value = [{"Id": "123"}, {"Id": "456"}]
    mock_get_details.return_value = [
        {"Linked account": "123"},
        {"Linked account": "456"},
    ]
    mock_get_spending.return_value = ["spending_data"]

    # Setup DataFrame mocks
    mock_spending_df = pd.DataFrame(
        [
            {"Linked account": "123", "Cost Amount": 100, "Period": "2025-03-01"},
            {"Linked account": "456", "Cost Amount": 200, "Period": "2025-03-01"},
        ]
    )
    mock_spending_to_df.return_value = mock_spending_df

    # Setup merged DataFrame
    mock_merged_df = pd.DataFrame(
        [
            {"Linked account": "123", "Cost Amount": 100, "Period": "2025-03-01"},
            {"Linked account": "456", "Cost Amount": 200, "Period": "2025-03-01"},
        ]
    )
    mock_merge.return_value = mock_merged_df

    # Call the function
    result = spending.generate_spending_data(mock_logger)

    # Assertions
    assert mock_list_accounts.called
    mock_get_details.assert_called_once_with(["123", "456"], mock_logger)
    assert mock_get_spending.called
    mock_spending_to_df.assert_called_once_with(["spending_data"])

    # Check for Converted Cost calculation
    assert "Converted Cost" in result.columns


@patch("modules.aws.spending.organizations.get_account_details")
@patch("modules.aws.spending.organizations.get_account_tags")
@patch("modules.aws.spending.format_account_details")
def test_get_accounts_details(mock_format, mock_get_tags, mock_get_details):
    """Test the get_accounts_details function."""
    # Setup mocks
    mock_logger = MagicMock()
    mock_get_details.return_value = {"Id": "123", "Name": "Test Account"}
    mock_get_tags.return_value = [{"Key": "business_unit", "Value": "HR"}]
    mock_format.return_value = {
        "Linked account": "123",
        "Linked account name": "Test Account",
        "Business Unit": "HR",
        "Product": "Unknown",
    }

    # Call the function
    result = spending.get_accounts_details(["123", "456"], mock_logger)

    # Assertions
    assert len(result) == 2
    mock_get_details.assert_has_calls([call("123"), call("456")])
    mock_get_tags.assert_has_calls([call("123"), call("456")])
    assert mock_format.call_count == 2


@patch("modules.aws.spending.cost_explorer.get_cost_and_usage")
def test_get_accounts_spending(mock_get_cost):
    """Test the get_accounts_spending function."""
    # Setup mocks
    current_year = "2025"
    current_month = "03"
    mock_response = {
        "ResultsByTime": [{"TimePeriod": {"Start": "2025-03-01", "End": "2025-03-31"}}]
    }
    mock_get_cost.return_value = mock_response

    # Call the function
    result = spending.get_accounts_spending(current_year, current_month, span=1)

    # Assertions
    assert result == [{"TimePeriod": {"Start": "2025-03-01", "End": "2025-03-31"}}]
    assert mock_get_cost.called


def test_get_rate_for_period():
    """Test the get_rate_for_period function."""
    # Test existing period
    rate = spending.get_rate_for_period("2025-03-01")
    assert rate == 1.4591369

    # Test non-existing period
    rate = spending.get_rate_for_period("2023-01-01")
    assert rate == 1.4591369  # Fallback rate


def test_format_account_details():
    """Test the format_account_details function."""
    # Test with both tags present
    account = {
        "Id": "123",
        "Name": "Test Account",
        "Tags": [
            {"Key": "business_unit", "Value": "HR"},
            {"Key": "product", "Value": "Payroll"},
        ],
    }
    result = spending.format_account_details(account)
    expected = {
        "Linked account": "123",
        "Linked account name": "Test Account",
        "Product": "Payroll",
        "Business Unit": "HR",
    }
    assert result == expected

    # Test with no tags
    account = {"Id": "123", "Name": "Test Account"}
    result = spending.format_account_details(account)
    expected = {
        "Linked account": "123",
        "Linked account name": "Test Account",
        "Product": "Unknown",
        "Business Unit": "Unknown",
    }
    assert result == expected


def test_spending_to_df_with_data():
    """Test the spending_to_df function with valid data."""
    spending_data = [
        {
            "TimePeriod": {"Start": "2025-03-01", "End": "2025-03-31"},
            "Groups": [
                {
                    "Keys": ["123", "EC2"],
                    "Metrics": {"UnblendedCost": {"Amount": "100.0", "Unit": "USD"}},
                }
            ],
        }
    ]
    result = spending.spending_to_df(spending_data)

    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    assert result.iloc[0]["Linked account"] == "123"
    assert result.iloc[0]["Service"] == "EC2"
    assert result.iloc[0]["Cost Amount"] == 100.0


def test_spending_to_df_empty_data():
    """Test the spending_to_df function with empty data."""
    # Test with empty list
    result = spending.spending_to_df([])
    assert result.empty

    # Test with data but no groups
    result = spending.spending_to_df(
        [{"TimePeriod": {"Start": "2025-03-01"}, "Groups": []}]
    )
    assert result.empty


@patch("modules.aws.spending.sheets.batch_update_values")
def test_update_spending_data(mock_batch_update):
    """Test the update_spending_data function."""
    # Create test DataFrame
    df = pd.DataFrame(
        [
            {"Linked account": "123", "Cost Amount": 100},
            {"Linked account": "456", "Cost Amount": 200},
        ]
    )

    # Call the function
    spending.update_spending_data(df)

    # Assertions
    assert mock_batch_update.called
    args, kwargs = mock_batch_update.call_args
    assert kwargs["spreadsheetId"] == spending.SPENDING_SHEET_ID
    assert kwargs["range"] == "Sheet1"
    assert kwargs["valueInputOption"] == "USER_ENTERED"

    # Check values format
    values = kwargs["values"]
    assert len(values) == 3  # Header + 2 rows
    assert values[0] == ["Linked account", "Cost Amount"]

    # Check that the data rows were properly added
    assert len(values[1:]) == 2  # Two data rows
    assert values[1][0] == "123"  # First row, first column
    assert values[1][1] == 100  # First row, second column
    assert values[2][0] == "456"  # Second row, first column
    assert values[2][1] == 200  # Second row, second column


@patch("modules.aws.spending.sheets.batch_update_values")
def test_update_spending_data_with_fallback(mock_batch_update):
    """Test the update_spending_data function with fallback path."""
    # Create a fully-mocked DataFrame
    mock_df = MagicMock()

    # Configure the mock's structure
    mock_df.columns.tolist.return_value = ["Linked account", "Cost Amount"]

    # Make values.tolist() return a non-list to trigger the fallback
    mock_values = MagicMock()
    mock_values.tolist.return_value = "not a list"
    mock_df.values = mock_values

    # Create mock Series objects for the rows
    mock_row1 = MagicMock()
    mock_row1.__getitem__.side_effect = lambda x: (
        "123" if x == "Linked account" else 100
    )
    mock_row1.tolist.return_value = ["123", 100]

    mock_row2 = MagicMock()
    mock_row2.__getitem__.side_effect = lambda x: (
        "456" if x == "Linked account" else 200
    )
    mock_row2.tolist.return_value = ["456", 200]

    # Set up iterrows to return tuples with our mock Series
    mock_df.iterrows.return_value = [(0, mock_row1), (1, mock_row2)]

    # Capture print output
    with patch("builtins.print") as mock_print:
        # Call the function with our mock DataFrame
        spending.update_spending_data(mock_df)

        # Verify warning was printed
        assert mock_print.called
        assert "Warning: DataFrame values conversion issue" in str(
            mock_print.call_args[0][0]
        )

    # Verify batch_update_values was called with correct values
    assert mock_batch_update.called
    args, kwargs = mock_batch_update.call_args
    values = kwargs["values"]

    # Verify we have header + 2 data rows
    assert len(values) == 3
    assert values[0] == ["Linked account", "Cost Amount"]
    assert values[1] == ["123", 100]
    assert values[2] == ["456", 200]
