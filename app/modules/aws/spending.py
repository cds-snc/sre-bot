"""Module to get AWS spending data."""

from datetime import datetime

import pandas as pd
from pandas.core.frame import DataFrame

from integrations.aws import organizations, cost_explorer
from integrations.google_workspace import sheets
from core.config import settings

SPENDING_SHEET_ID = settings.aws_feature.SPENDING_SHEET_ID

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


def generate_spending_data(logger):
    """Generates the spending data for all accounts and returns a DataFrame"""
    year, month = datetime.now().strftime("%Y"), datetime.now().strftime("%m")
    logger.info("generating_aws_spending_data", year=year, month=month)
    account_ids = list(
        map(lambda account: account["Id"], organizations.list_organization_accounts())
    )
    logger.info("aws_accounts_listed", count=len(account_ids))
    accounts = get_accounts_details(account_ids, logger)
    accounts_df = pd.DataFrame(accounts)
    logger.info("aws_spending_data_request", year=year, month=month)
    spending = get_accounts_spending(year, month)
    spending_df = spending_to_df(spending, logger)
    merged_df = pd.merge(accounts_df, spending_df, on="Linked account", how="inner")
    merged_df["Converted Cost"] = merged_df.apply(
        lambda row: row["Cost Amount"] * get_rate_for_period(row["Period"]),
        axis=1,
    )
    return merged_df


def get_accounts_details(ids, logger):
    """Returns the details for the specified account IDs"""
    accounts = []
    for id in ids:
        logger.info("aws_account_details_request", account_id=id)
        details = organizations.get_account_details(id)
        account_tags = organizations.get_account_tags(id)
        details["Tags"] = account_tags
        account = format_account_details(details)
        accounts.append(account)
    return accounts


def get_accounts_spending(year, month, span=12):
    """Returns the spending data for the specified year and month"""
    results = []
    for i in range(span):
        start_date = pd.Timestamp(f"{year}-{month}-01") - pd.DateOffset(months=i)
        end_date = start_date + pd.offsets.MonthEnd(1)
        time_period = {
            "Start": start_date.strftime("%Y-%m-%d"),
            "End": end_date.strftime("%Y-%m-%d"),
        }
        response = cost_explorer.get_cost_and_usage(
            time_period=time_period,
            granularity="MONTHLY",
            metrics=["UnblendedCost"],
            group_by=[
                {"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"},
                {"Type": "DIMENSION", "Key": "SERVICE"},
            ],
        )
        results.extend(response.get("ResultsByTime", []))
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


def spending_to_df(spending: list, logger):
    """Converts the spending data to a pandas DataFrame with flattened structure"""
    if not spending:
        logger.warning("spending_to_df", error="No spending data provided")
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
        logger.warning(
            "spending_to_df",
            error="No spending data available after flattening",
        )
        return pd.DataFrame()

    return pd.DataFrame(flattened_data)


def update_spending_data(
    spending_data_df: DataFrame, logger, spreadsheet_id=SPENDING_SHEET_ID
):
    """
    Updates the entire Sheet1 with new spending data

    Args:
        spending_data_df: pandas DataFrame containing the data to upload
    """
    if not spreadsheet_id:
        logger.error("update_spending_data", error="SPENDING_SHEET_ID is not set")
        return

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
        logger.warning(
            "data_values_is_not_list",
            actual_type=str(type(data_values)),
        )
        # Alternative approach if needed:
        for _, row in spending_data_df.iterrows():
            values.append(row.tolist())

    # Update the entire sheet with new values
    sheets.batch_update_values(
        spreadsheetId=spreadsheet_id,
        cell_range="Sheet1",
        values=values,
        valueInputOption="USER_ENTERED",
    )
    logger.info("update_spending_data", spreadsheet_id=spreadsheet_id)


def execute_spending_data_update_job(logger):
    """Executes the spending data update job"""
    logger.info("execute_spending_data_update_job", status="started")
    spending_data = generate_spending_data(logger)
    if spending_data.empty:
        logger.error(
            "execute_spending_data_update_job",
            status="failed",
            error="No spending data generated",
        )
        return
    update_spending_data(spending_data, logger)
    logger.info(
        "execute_spending_data_update_job",
        status="success",
        spreadsheet_id=SPENDING_SHEET_ID,
    )
