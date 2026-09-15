"""Module to get AWS spending data."""

from datetime import datetime
from typing import Any

import pandas as pd
import structlog
from pandas.core.frame import DataFrame

from infrastructure.configuration.integrations.google import (
    get_google_resources_config,
)
from infrastructure.operations import OperationResult
from infrastructure.spreadsheets import get_spreadsheet_provider
from packages.aws_platform.adapters.cost_explorer import CostExplorerAdapter, build_cost_explorer_adapter
from packages.aws_platform.adapters.organizations import OrganizationsAdapter, build_organizations_adapter

logger = structlog.get_logger()


rates = {
    "2025-03-01": {"rate": 1.4591369, "confirmed": False},
    "2025-02-01": {"rate": 1.4591369, "confirmed": True},
    "2025-01-01": {"rate": 1.4637728, "confirmed": True},
    "2024-12-01": {"rate": 1.4493904, "confirmed": True},
    "2024-11-01": {"rate": 1.3671, "confirmed": True},
    "2024-10-01": {"rate": 1.3671, "confirmed": True},
    "2024-09-01": {"rate": 1.3671, "confirmed": True},
    "2024-08-01": {"rate": 1.3671, "confirmed": True},
    "2024-07-01": {"rate": 1.39870853, "confirmed": True},
    "2024-06-01": {"rate": 1.3671, "confirmed": True},
    "2024-05-01": {"rate": 1.3821042, "confirmed": True},
    "2024-04-01": {"rate": 1.380468, "confirmed": True},
    "fallback": {"rate": 1.4591369, "confirmed": False},
}


def _failure_fields(result: OperationResult[Any]) -> dict[str, Any]:
    """Return the structured log fields describing a non-success adapter result."""
    return {"status": result.status.value, "error_code": result.error_code, "error": result.message}


def generate_spending_data() -> DataFrame | None:
    """Generates the spending data for all accounts and returns a DataFrame.

    Returns None when an AWS lookup fails, so a partial report never replaces the
    sheet, and an empty DataFrame when there is nothing to report.
    """
    year, month = datetime.now().strftime("%Y"), datetime.now().strftime("%m")
    log = logger.bind(year=year, month=month)
    log.info("generating_aws_spending_data")
    organizations_adapter = build_organizations_adapter()
    cost_explorer_adapter = build_cost_explorer_adapter()

    accounts_result = organizations_adapter.list_organization_accounts()
    if not accounts_result.is_success:
        log.error("aws_accounts_list_failed", **_failure_fields(accounts_result))
        return None
    account_ids = [account["Id"] for account in accounts_result.data or []]
    log.info("aws_accounts_listed", count=len(account_ids))
    accounts = get_accounts_details(organizations_adapter, account_ids)
    if accounts is None:
        return None
    if not accounts:
        log.warning("aws_spending_data_empty", reason="no accounts")
        return pd.DataFrame()

    log.info("aws_spending_data_request")
    spending = get_accounts_spending(cost_explorer_adapter, year, month)
    if spending is None:
        return None
    spending_df = spending_to_df(spending)
    if spending_df.empty:
        log.warning("aws_spending_data_empty", reason="no spending")
        return pd.DataFrame()

    accounts_df = pd.DataFrame(accounts)
    merged_df = pd.merge(accounts_df, spending_df, on="Linked account", how="inner")
    merged_df["Converted Cost"] = merged_df.apply(
        lambda row: row["Cost Amount"] * get_rate_for_period(row["Period"]),
        axis=1,
    )
    return merged_df


def get_accounts_details(organizations_adapter: OrganizationsAdapter, ids: list[str]) -> list[dict[str, str]] | None:
    """Returns the details for the specified account IDs.

    Returns None when an account cannot be described. A failed tag lookup keeps
    the account with an Unknown product and business unit.
    """
    accounts = []
    for account_id in ids:
        log = logger.bind(account_id=account_id)
        log.info("aws_account_details_request")
        details_result = organizations_adapter.get_account_details(account_id)
        if not details_result.is_success or details_result.data is None:
            log.error("aws_account_details_failed", **_failure_fields(details_result))
            return None
        tags_result = organizations_adapter.get_account_tags(account_id)
        if not tags_result.is_success:
            log.warning("aws_account_tags_failed", **_failure_fields(tags_result))
        tags = tags_result.data if tags_result.is_success and tags_result.data else []
        accounts.append(format_account_details({**details_result.data, "Tags": tags}))
    return accounts


def get_accounts_spending(
    cost_explorer_adapter: CostExplorerAdapter, year: str, month: str, span: int = 12
) -> list[dict[str, Any]] | None:
    """Returns the spending data for the specified year and month and the preceding months.

    Returns None as soon as one month fails, so an incomplete window is never reported.
    """
    results: list[dict[str, Any]] = []
    for i in range(span):
        start_date = pd.Timestamp(f"{year}-{month}-01") - pd.DateOffset(months=i)
        # Cost Explorer's End is exclusive: the first day of the next month keeps the last day's cost.
        end_date = start_date + pd.offsets.MonthBegin(1)
        time_period = {
            "Start": start_date.strftime("%Y-%m-%d"),
            "End": end_date.strftime("%Y-%m-%d"),
        }
        result = cost_explorer_adapter.get_cost_and_usage(
            time_period=time_period,
            granularity="MONTHLY",
            metrics=["UnblendedCost"],
            group_by=[
                {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        )
        if not result.is_success:
            logger.error(
                "aws_cost_and_usage_failed",
                start=time_period["Start"],
                end=time_period["End"],
                **_failure_fields(result),
            )
            return None
        results.extend(result.data or [])
    return results


def get_rate_for_period(period):
    """Returns the exchange rate for the specified period"""
    if period in rates:
        return rates[period]["rate"]
    return rates["fallback"]["rate"]


def format_account_details(account):
    """Returns the account details to a streamlined format"""
    business_unit = "Unknown"
    product = "Unknown"
    if "Tags" in account:
        for tag in account["Tags"]:
            if tag["Key"] == "business_unit":
                business_unit = tag["Value"]
            if tag["Key"] == "product":
                product = tag["Value"]
    return {
        "Linked account": account["Id"],
        "Linked account name": account["Name"],
        "Product": product,
        "Business Unit": business_unit,
    }


def spending_to_df(spending: list):
    """Converts the spending data to a pandas DataFrame with flattened structure."""
    log = logger.bind()
    if not spending:
        log.warning("spending_to_df", error="No spending data provided")
        return pd.DataFrame()

    flattened_data = []
    for month in spending:
        time_period = month["TimePeriod"]["Start"]
        groups = month.get("Groups", [])
        for group in groups:
            flattened_data.append(
                {
                    "Linked account": group["Keys"][0],
                    "Service": group["Keys"][1],
                    "Cost Amount": float(group["Metrics"]["UnblendedCost"]["Amount"]),
                    "Cost Unit": group["Metrics"]["UnblendedCost"]["Unit"],
                    "Period": time_period,
                }
            )

    if not flattened_data:
        log.warning(
            "spending_to_df",
            error="No spending data available after flattening",
        )
        return pd.DataFrame()

    return pd.DataFrame(flattened_data)


def update_spending_data(
    spending_data_df: DataFrame,
    spreadsheet_id: str | None = None,
) -> bool:
    """
    Updates the entire Sheet1 with new spending data.

    Args:
        spending_data_df: pandas DataFrame containing the data to upload
        spreadsheet_id: Google Sheets spreadsheet ID; resolved from config when omitted

    Returns:
        True if the write succeeded, False if it was skipped or failed.
    """
    if spreadsheet_id is None:
        spreadsheet_id = get_google_resources_config().spending_sheet_id
    log = logger.bind(spreadsheet_id=spreadsheet_id)
    if not spreadsheet_id:
        log.error("update_spending_data", error="spending sheet id is not set")
        return False

    # Convert DataFrame to list of lists for Google Sheets API
    header = spending_data_df.columns.tolist()

    # Ensure values is a list of lists
    data_values = spending_data_df.values.tolist()

    # Combine header and data
    values = [header]
    if isinstance(data_values, list):
        values.extend(data_values)
    else:
        # Handle the case where values.tolist() might not return a list
        log.warning(
            "data_values_is_not_list",
            actual_type=str(type(data_values)),
        )
        # Alternative approach if needed:
        for _, row in spending_data_df.iterrows():
            values.append(row.tolist())

    # Temporary shim until AWS spending reporting is rearchitected into a feature package.
    result = get_spreadsheet_provider().update_values(spreadsheet_id, "Sheet1", values)
    if not result.is_success:
        log.error(
            "update_spending_data_failed",
            status=result.status.value,
            error_code=result.error_code,
            message=result.message,
        )
        return False

    log.info("update_spending_data")
    return True


def execute_spending_data_update_job() -> None:
    """Executes the spending data update job"""
    log = logger.bind()
    log.info("execute_spending_data_update_job", status="started")
    spending_data = generate_spending_data()
    if spending_data is None:
        log.warning(
            "execute_spending_data_update_job",
            status="failed",
            message="Spending data generation failed",
        )
        return
    if spending_data.empty:
        log.warning(
            "execute_spending_data_update_job",
            status="no_data",
            message="No spending data to update",
        )
        return
    updated = update_spending_data(spending_data)
    if not updated:
        log.warning(
            "execute_spending_data_update_job",
            status="failed",
            message="Spending data update did not complete",
        )
        return
    log.info("execute_spending_data_update_job", status="success")
