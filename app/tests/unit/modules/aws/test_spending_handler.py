"""Unit tests for AWS spending data handler."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.spreadsheets import SpreadsheetProvider
from modules.aws import spending


@pytest.fixture
def spreadsheet_provider():
    """Patch the spending module's provider lookup with a Protocol-shaped double.

    The double defaults to a successful write so happy-path tests assert on the
    values matrix handed to the provider rather than on transport details.
    """
    provider = MagicMock(spec=SpreadsheetProvider)
    provider.update_values.return_value = OperationResult.success()
    with patch("modules.aws.spending.get_spreadsheet_provider", return_value=provider):
        yield provider


@pytest.mark.unit
@patch("modules.aws.spending.organizations")
def test_should_generate_spending_data_successfully(mock_organizations):
    """Test successful spending data generation."""
    # Arrange
    mock_organizations.list_organization_accounts.return_value = [{"Id": "123456789012", "Name": "TestAccount"}]

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
    spending_data: list[dict[str, object]] = []

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
def test_should_update_spending_data_in_sheet(spreadsheet_provider):
    """Test that a successful write reaches the spreadsheet provider and reports success."""
    # Arrange
    data = {"Account": ["123456789012"], "Cost": [100.00]}
    df = pd.DataFrame(data)

    # Act
    result = spending.update_spending_data(df, spreadsheet_id="test_sheet_id")

    # Assert
    spreadsheet_provider.update_values.assert_called_once_with(
        "test_sheet_id",
        "Sheet1",
        [["Account", "Cost"], ["123456789012", 100.00]],
    )
    assert result is True


@pytest.mark.unit
@patch("modules.aws.spending.get_google_resources_config")
def test_should_skip_update_when_spreadsheet_id_not_set(mock_get_config, spreadsheet_provider):
    """Test that the write is skipped when the configured spreadsheet ID is empty.

    The configuration lookup is stubbed rather than the module attribute because
    the ID is resolved per call, not bound at import time.
    """
    # Arrange
    mock_get_config.return_value = SimpleNamespace(spending_sheet_id="")
    df = pd.DataFrame({"Account": ["123456789012"], "Cost": [100.00]})

    # Act
    result = spending.update_spending_data(df)

    # Assert
    spreadsheet_provider.update_values.assert_not_called()
    assert result is False


@pytest.mark.unit
def test_should_skip_update_when_spreadsheet_id_is_empty_string(spreadsheet_provider):
    """Test that update is skipped when the spreadsheet ID is an empty string."""
    # Arrange
    df = pd.DataFrame({"Account": ["123456789012"], "Cost": [100.00]})

    # Act
    result = spending.update_spending_data(df, spreadsheet_id="")

    # Assert
    spreadsheet_provider.update_values.assert_not_called()
    assert result is False


@pytest.mark.unit
@patch("modules.aws.spending.get_google_resources_config")
def test_should_resolve_spreadsheet_id_from_config_on_every_call(mock_get_config, spreadsheet_provider):
    """Test that an omitted spreadsheet ID is read from configuration on each call.

    Two successive calls see two different configured IDs; asserting both reach
    the provider proves the ID is not cached from the first resolution.
    """
    # Arrange
    df = pd.DataFrame({"Account": ["123456789012"], "Cost": [100.00]})
    mock_get_config.side_effect = [
        SimpleNamespace(spending_sheet_id="first_sheet_id"),
        SimpleNamespace(spending_sheet_id="second_sheet_id"),
    ]

    # Act
    spending.update_spending_data(df)
    spending.update_spending_data(df)

    # Assert
    used_ids = [call.args[0] for call in spreadsheet_provider.update_values.call_args_list]
    assert used_ids == ["first_sheet_id", "second_sheet_id"]


@pytest.mark.unit
def test_should_send_header_row_followed_by_dataframe_rows_to_sheets(spreadsheet_provider):
    """Test the exact values matrix crossing the spreadsheet boundary."""
    # Arrange
    df = pd.DataFrame({"Account": ["123456789012", "210987654321"], "Cost": [100.00, 250.50]})

    # Act
    spending.update_spending_data(df, spreadsheet_id="test_sheet_id")

    # Assert
    values = spreadsheet_provider.update_values.call_args.args[2]
    assert values == [
        ["Account", "Cost"],
        ["123456789012", 100.00],
        ["210987654321", 250.50],
    ]


@pytest.mark.unit
def test_should_send_header_row_only_when_dataframe_has_no_rows(spreadsheet_provider):
    """Test that an empty but columned DataFrame sends just the header."""
    # Arrange
    df = pd.DataFrame(columns=["Account", "Cost"])

    # Act
    spending.update_spending_data(df, spreadsheet_id="test_sheet_id")

    # Assert
    values = spreadsheet_provider.update_values.call_args.args[2]
    assert values == [["Account", "Cost"]]


@pytest.mark.unit
@patch("modules.aws.spending.logger")
def test_should_log_and_return_false_when_sheets_update_fails(mock_logger, spreadsheet_provider):
    """Test that a classified write failure is logged and contained.

    The logger is stubbed at the module level; the module binds context before
    logging, so assertions target the bound logger returned by ``bind``.
    """
    # Arrange
    df = pd.DataFrame({"Account": ["123456789012"], "Cost": [100.00]})
    spreadsheet_provider.update_values.return_value = OperationResult.error(
        status=OperationStatus.TRANSIENT_ERROR,
        message="sheets down",
        error_code="RATE_LIMITED",
    )

    # Act
    result = spending.update_spending_data(df, spreadsheet_id="test_sheet_id")

    # Assert
    assert result is False
    mock_logger.bind.return_value.error.assert_called_once_with(
        "update_spending_data_failed",
        status="transient_error",
        error_code="RATE_LIMITED",
        message="sheets down",
    )


@pytest.mark.unit
@patch("modules.aws.spending.logger")
@patch("modules.aws.spending.generate_spending_data")
@patch("modules.aws.spending.update_spending_data")
def test_should_execute_and_update_spending_job_successfully(mock_update, mock_generate, mock_logger):
    """Test successful execution of spending data update job."""
    # Arrange
    mock_spending_data = pd.DataFrame({"Account": ["123456789012"], "Cost": [100.00]})
    mock_generate.return_value = mock_spending_data
    mock_update.return_value = True

    # Act
    spending.execute_spending_data_update_job()

    # Assert
    mock_generate.assert_called_once()
    mock_update.assert_called_once_with(mock_spending_data)
    bound_logger = mock_logger.bind.return_value
    bound_logger.info.assert_any_call("execute_spending_data_update_job", status="success")
    assert not [call for call in bound_logger.warning.call_args_list if call.kwargs.get("status") == "failed"]


@pytest.mark.unit
@patch("modules.aws.spending.logger")
@patch("modules.aws.spending.generate_spending_data")
@patch("modules.aws.spending.update_spending_data")
def test_should_log_failed_run_when_update_spending_data_fails(mock_update, mock_generate, mock_logger):
    """Test that a failed write makes the scheduled job log a failed run instead of raising."""
    # Arrange
    mock_spending_data = pd.DataFrame({"Account": ["123456789012"], "Cost": [100.00]})
    mock_generate.return_value = mock_spending_data
    mock_update.return_value = False

    # Act
    spending.execute_spending_data_update_job()

    # Assert
    bound_logger = mock_logger.bind.return_value
    failed_calls = [
        call
        for call in bound_logger.warning.call_args_list
        if call.args == ("execute_spending_data_update_job",) and call.kwargs.get("status") == "failed"
    ]
    assert len(failed_calls) == 1
    bound_logger.info.assert_called_once_with("execute_spending_data_update_job", status="started")


@pytest.mark.unit
@patch("modules.aws.spending.generate_spending_data")
@patch("modules.aws.spending.update_spending_data")
def test_should_skip_update_when_spending_data_empty(mock_update, mock_generate):
    """Test that update is skipped when spending data is empty."""
    # Arrange
    mock_spending_data = pd.DataFrame()
    mock_generate.return_value = mock_spending_data

    # Act
    spending.execute_spending_data_update_job()

    # Assert
    mock_generate.assert_called_once()
    mock_update.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.spending.organizations")
def test_should_raise_when_list_organization_accounts_returns_false(mock_organizations):
    """Test generate_spending_data surfaces a TypeError when organizations returns False.

    Stub strategy: list_organization_accounts returns the literal False that
    handle_aws_api_errors produces on error; the list comprehension iterating over
    accounts pins today's crash on a non-iterable bool.
    """
    # Arrange
    mock_organizations.list_organization_accounts.return_value = False

    # Act & Assert
    with pytest.raises(TypeError):
        spending.generate_spending_data()


@pytest.mark.unit
@patch("modules.aws.spending.organizations")
def test_should_raise_when_get_account_details_returns_false(mock_organizations):
    """Test get_accounts_details surfaces a TypeError when get_account_details returns False.

    Stub strategy: get_account_details returns False; the subsequent item assignment
    `details["Tags"] = ...` on a bool pins today's crash.
    """
    # Arrange
    mock_organizations.get_account_details.return_value = False
    mock_organizations.get_account_tags.return_value = []

    # Act & Assert
    with pytest.raises(TypeError):
        spending.get_accounts_details(["123456789012"])


@pytest.mark.unit
@patch("modules.aws.spending.organizations")
def test_should_raise_when_get_account_tags_returns_false(mock_organizations):
    """Test get_accounts_details surfaces a TypeError when get_account_tags returns False.

    Stub strategy: get_account_details succeeds but get_account_tags returns False;
    the crash actually happens inside format_account_details' `for tag in account["Tags"]`,
    reached from get_accounts_details, so the raise is asserted at the caller.
    """
    # Arrange
    mock_organizations.get_account_details.return_value = {"Id": "123456789012", "Name": "TestAccount"}
    mock_organizations.get_account_tags.return_value = False

    # Act & Assert
    with pytest.raises(TypeError):
        spending.get_accounts_details(["123456789012"])


@pytest.mark.unit
@patch("modules.aws.spending.cost_explorer")
def test_should_raise_when_cost_and_usage_returns_false(mock_cost_explorer):
    """Test get_accounts_spending surfaces an AttributeError when cost_explorer returns False.

    Stub strategy: get_cost_and_usage returns the literal False; the subsequent
    `response.get(...)` call on a bool pins today's crash.
    """
    # Arrange
    mock_cost_explorer.get_cost_and_usage.return_value = False

    # Act & Assert
    with pytest.raises(AttributeError):
        spending.get_accounts_spending("2024", "01", span=1)
