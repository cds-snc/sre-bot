"""Unit tests for AWS spending data handler."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from infrastructure.operations import OperationResult, OperationStatus
from infrastructure.spreadsheets import SpreadsheetProvider
from modules.aws import spending

ACCOUNT_ID = "123456789012"


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


def _failure(message: str = "access denied", error_code: str = "AccessDeniedException") -> OperationResult[Any]:
    """Return a classified adapter failure."""
    return OperationResult.error(OperationStatus.UNAUTHORIZED, message=message, error_code=error_code)


def _cost_entry(start: str, account_id: str = ACCOUNT_ID, service: str = "s3", amount: str = "100.00") -> dict[str, Any]:
    """Return one Cost Explorer ResultsByTime entry holding a single account/service group."""
    return {
        "TimePeriod": {"Start": start},
        "Groups": [
            {
                "Keys": [account_id, service],
                "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}},
            }
        ],
    }


def _logged(mock_logger: MagicMock, event: str) -> list[dict[str, Any]]:
    """Return the keyword arguments of every log call for ``event``, whether made on the logger or a bound child."""
    return [dict(entry.kwargs) for entry in mock_logger.mock_calls if entry.args[:1] == (event,)]


def _logged_failure(mock_logger: MagicMock, event: str, message: str = "access denied") -> bool:
    """Whether ``event`` was logged carrying the classified status, error code and adapter message."""
    return any(
        kwargs.get("status") == OperationStatus.UNAUTHORIZED.value
        and kwargs.get("error_code") == "AccessDeniedException"
        and kwargs.get("error") == message
        for kwargs in _logged(mock_logger, event)
    )


def _arrange_account(organizations_adapter: MagicMock, tags: list[dict[str, str]] | None = None) -> None:
    """Stub a single organization account whose listing, details and tags all succeed."""
    organizations_adapter.list_organization_accounts.return_value = OperationResult.success(
        data=[{"Id": ACCOUNT_ID, "Name": "TestAccount"}]
    )
    organizations_adapter.get_account_details.return_value = OperationResult.success(
        data={"Id": ACCOUNT_ID, "Name": "TestAccount"}
    )
    organizations_adapter.get_account_tags.return_value = OperationResult.success(data=tags or [])


@pytest.mark.unit
@patch("modules.aws.spending.build_cost_explorer_adapter")
@patch("modules.aws.spending.build_organizations_adapter")
def test_should_generate_spending_data_successfully(mock_build_organizations_adapter, mock_build_cost_explorer_adapter):
    """Accounts, tags and cost groups from the adapters merge into one converted row per account and service.

    Stub strategy: both adapter factories return MagicMocks whose operations
    return successful OperationResults. Cost Explorer returns one group for the
    first queried month and no entries for the other eleven, so exactly one row
    survives the inner merge.
    """
    # Arrange
    _arrange_account(
        mock_build_organizations_adapter.return_value,
        tags=[{"Key": "product", "Value": "TestProduct"}, {"Key": "business_unit", "Value": "TestBU"}],
    )
    cost_explorer_adapter = mock_build_cost_explorer_adapter.return_value
    cost_explorer_adapter.get_cost_and_usage.side_effect = [OperationResult.success(data=[_cost_entry("2024-01-01")])] + [
        OperationResult.success(data=[]) for _ in range(11)
    ]

    # Act
    result = spending.generate_spending_data()

    # Assert
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
    row = result.iloc[0]
    assert row["Linked account"] == ACCOUNT_ID
    assert row["Product"] == "TestProduct"
    assert row["Business Unit"] == "TestBU"
    assert row["Converted Cost"] == pytest.approx(100.00 * spending.get_rate_for_period("2024-01-01"))
    assert cost_explorer_adapter.get_cost_and_usage.call_count == 12


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
@patch("modules.aws.spending.logger")
@patch("modules.aws.spending.generate_spending_data")
@patch("modules.aws.spending.update_spending_data")
def test_should_log_failed_run_without_writing_when_spending_generation_fails(mock_update, mock_generate, mock_logger):
    """A spending run whose generation aborted logs a failed run and never writes the sheet.

    Stub strategy: generate_spending_data returns None, the abort signal for an
    upstream AWS failure; the module logger is patched so the failed-run event
    is observable whether it is logged on the logger or a bound child.
    """
    # Arrange
    mock_generate.return_value = None

    # Act
    spending.execute_spending_data_update_job()

    # Assert
    mock_update.assert_not_called()
    assert any(kwargs.get("status") == "failed" for kwargs in _logged(mock_logger, "execute_spending_data_update_job"))


@pytest.mark.unit
@patch("modules.aws.spending.logger")
@patch("modules.aws.spending.build_cost_explorer_adapter")
@patch("modules.aws.spending.build_organizations_adapter")
def test_should_return_none_and_log_when_listing_organization_accounts_fails(
    mock_build_organizations_adapter, mock_build_cost_explorer_adapter, mock_logger
):
    """A failed account listing aborts the run before any account or cost lookup.

    Stub strategy: list_organization_accounts returns a classified UNAUTHORIZED
    failure. Returning None (rather than a partial DataFrame) is what keeps the
    fully replaced sheet from being overwritten with incomplete data.
    """
    # Arrange
    organizations_adapter = mock_build_organizations_adapter.return_value
    organizations_adapter.list_organization_accounts.return_value = _failure()

    # Act
    result = spending.generate_spending_data()

    # Assert
    assert result is None
    organizations_adapter.get_account_details.assert_not_called()
    mock_build_cost_explorer_adapter.return_value.get_cost_and_usage.assert_not_called()
    assert _logged_failure(mock_logger, "aws_accounts_list_failed")


@pytest.mark.unit
@patch("modules.aws.spending.logger")
@patch("modules.aws.spending.build_cost_explorer_adapter")
@patch("modules.aws.spending.build_organizations_adapter")
def test_should_return_none_and_log_when_account_details_lookup_fails(
    mock_build_organizations_adapter, mock_build_cost_explorer_adapter, mock_logger
):
    """A failed account description aborts the run instead of dropping that account's costs.

    Stub strategy: the listing succeeds with one account and get_account_details
    returns a classified failure; Cost Explorer is observed to prove the run
    stops before querying costs.
    """
    # Arrange
    organizations_adapter = mock_build_organizations_adapter.return_value
    _arrange_account(organizations_adapter)
    organizations_adapter.get_account_details.return_value = _failure()

    # Act
    result = spending.generate_spending_data()

    # Assert
    assert result is None
    mock_build_cost_explorer_adapter.return_value.get_cost_and_usage.assert_not_called()
    assert _logged_failure(mock_logger, "aws_account_details_failed")


@pytest.mark.unit
@patch("modules.aws.spending.logger")
def test_should_keep_account_with_unknown_tags_when_tag_lookup_fails(mock_logger):
    """A failed tag lookup keeps the account with Unknown product and business unit.

    Stub strategy: a MagicMock organizations adapter describes the account
    successfully but fails get_account_tags; the account must still be returned
    so its costs stay in the report, and the failure must be logged.
    """
    # Arrange
    organizations_adapter = MagicMock()
    _arrange_account(organizations_adapter)
    organizations_adapter.get_account_tags.return_value = _failure()

    # Act
    accounts = spending.get_accounts_details(organizations_adapter, [ACCOUNT_ID])

    # Assert
    assert accounts == [
        {
            "Linked account": ACCOUNT_ID,
            "Linked account name": "TestAccount",
            "Product": "Unknown",
            "Business Unit": "Unknown",
        }
    ]
    assert _logged_failure(mock_logger, "aws_account_tags_failed")


@pytest.mark.unit
@patch("modules.aws.spending.logger")
def test_should_stop_and_return_none_when_a_cost_and_usage_month_fails(mock_logger):
    """A failed Cost Explorer month stops the spending lookup and signals the abort with None.

    Stub strategy: the second of three monthly calls returns a classified
    failure; the call count proves no later month is queried once the window
    is known to be incomplete.
    """
    # Arrange
    cost_explorer_adapter = MagicMock()
    cost_explorer_adapter.get_cost_and_usage.side_effect = [
        OperationResult.success(data=[]),
        _failure(),
        OperationResult.success(data=[]),
    ]

    # Act
    result = spending.get_accounts_spending(cost_explorer_adapter, "2024", "03", span=3)

    # Assert
    assert result is None
    assert cost_explorer_adapter.get_cost_and_usage.call_count == 2
    assert _logged_failure(mock_logger, "aws_cost_and_usage_failed")


@pytest.mark.unit
@patch("modules.aws.spending.build_cost_explorer_adapter")
@patch("modules.aws.spending.build_organizations_adapter")
def test_should_return_none_when_cost_and_usage_fails_during_generation(
    mock_build_organizations_adapter, mock_build_cost_explorer_adapter
):
    """A Cost Explorer failure makes the whole spending generation abort with None.

    Stub strategy: account lookups succeed and the first get_cost_and_usage call
    fails, so no partial spending window can reach the merge.
    """
    # Arrange
    _arrange_account(mock_build_organizations_adapter.return_value)
    mock_build_cost_explorer_adapter.return_value.get_cost_and_usage.return_value = _failure()

    # Act
    result = spending.generate_spending_data()

    # Assert
    assert result is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("year", "month", "span", "expected_periods"),
    [
        pytest.param(
            "2025",
            "01",
            2,
            [
                {"Start": "2025-01-01", "End": "2025-02-01"},
                {"Start": "2024-12-01", "End": "2025-01-01"},
            ],
            id="year-rollover",
        ),
        pytest.param("2024", "02", 1, [{"Start": "2024-02-01", "End": "2024-03-01"}], id="leap-february"),
    ],
)
def test_should_query_each_month_with_exclusive_end_on_first_day_of_next_month(year, month, span, expected_periods):
    """Each monthly Cost Explorer query ends on the first day of the following month.

    Cost Explorer treats TimePeriod.End as exclusive, so ending on the last
    calendar day would drop that day's cost. Stub strategy: a MagicMock adapter
    returning empty successes; assertions read the time_period of every call.
    """
    # Arrange
    cost_explorer_adapter = MagicMock()
    cost_explorer_adapter.get_cost_and_usage.return_value = OperationResult.success(data=[])

    # Act
    spending.get_accounts_spending(cost_explorer_adapter, year, month, span=span)

    # Assert
    periods = [call.kwargs["time_period"] for call in cost_explorer_adapter.get_cost_and_usage.call_args_list]
    assert periods == expected_periods


@pytest.mark.unit
def test_should_keep_every_entry_when_one_month_spans_several_result_entries():
    """Entries sharing a TimePeriod (as paginated GroupBy results do) are all kept and flattened.

    Stub strategy: one month returns two entries for the same period carrying
    different service groups; both must reach the flattened DataFrame.
    """
    # Arrange
    cost_explorer_adapter = MagicMock()
    cost_explorer_adapter.get_cost_and_usage.return_value = OperationResult.success(
        data=[_cost_entry("2024-01-01", service="s3"), _cost_entry("2024-01-01", service="ec2")]
    )

    # Act
    results = spending.get_accounts_spending(cost_explorer_adapter, "2024", "01", span=1)

    # Assert
    assert results is not None
    assert sorted(spending.spending_to_df(results)["Service"]) == ["ec2", "s3"]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("accounts", "cost_entries"),
    [
        pytest.param([], [_cost_entry("2024-01-01")], id="no-accounts"),
        pytest.param([{"Id": ACCOUNT_ID, "Name": "TestAccount"}], [], id="no-spending"),
    ],
)
@patch("modules.aws.spending.build_cost_explorer_adapter")
@patch("modules.aws.spending.build_organizations_adapter")
def test_should_return_empty_dataframe_when_accounts_or_spending_are_empty(
    mock_build_organizations_adapter, mock_build_cost_explorer_adapter, accounts, cost_entries
):
    """Successful but empty account or spending data yields an empty DataFrame rather than a merge error.

    Stub strategy: every adapter call succeeds; one side of the merge is empty.
    An empty DataFrame (not None) distinguishes "nothing to report" from an
    aborted run.
    """
    # Arrange
    organizations_adapter = mock_build_organizations_adapter.return_value
    _arrange_account(organizations_adapter)
    organizations_adapter.list_organization_accounts.return_value = OperationResult.success(data=accounts)
    mock_build_cost_explorer_adapter.return_value.get_cost_and_usage.return_value = OperationResult.success(data=cost_entries)

    # Act
    result = spending.generate_spending_data()

    # Assert
    assert isinstance(result, pd.DataFrame)
    assert result.empty
