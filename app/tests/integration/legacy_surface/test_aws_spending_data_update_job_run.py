"""Pins what the daily AWS spending job writes to the spending spreadsheet.

The job entry point is called directly. Only the external edges are faked:
the Organizations and Cost Explorer adapters (patched where the legacy module
binds their builders), the spreadsheet provider, and the sheet id through its
environment variable. The Cost Explorer fake labels each month with the
period it was asked for, so no assertion depends on the current date.
Assertions are on the single spreadsheet write the provider receives.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from contracts.operations import OperationResult, OperationStatus
from features.cloud_operations.spending.settings import get_cloud_operations_spending_settings
from modules.aws import spending
from modules.aws.spending import execute_spending_data_update_job as run_spending_job

pytestmark = pytest.mark.integration

SHEET_ID = "sheet-spending-1"
HEADER = [
    "Linked account",
    "Linked account name",
    "Product",
    "Business Unit",
    "Service",
    "Cost Amount",
    "Cost Unit",
    "Period",
    "Converted Cost",
]
DENIED = OperationResult.error(OperationStatus.UNAUTHORIZED, message="denied", error_code="AccessDeniedException")


class FakeOrganizations:
    """Organizations adapter double over a fixed set of accounts with optional tags."""

    def __init__(self) -> None:
        self.accounts: dict[str, dict[str, Any]] = {}
        self.fail_listing = False
        self.fail_details_for: set[str] = set()
        self.fail_tags = False

    def list_organization_accounts(self) -> OperationResult[list[dict[str, Any]]]:
        if self.fail_listing:
            return DENIED
        return OperationResult.success(
            [{"Id": account_id, "Name": account["Name"]} for account_id, account in self.accounts.items()]
        )

    def get_account_details(self, account_id: str) -> OperationResult[dict[str, Any]]:
        if account_id in self.fail_details_for:
            return DENIED
        return OperationResult.success({"Id": account_id, "Name": self.accounts[account_id]["Name"]})

    def get_account_tags(self, account_id: str) -> OperationResult[list[dict[str, str]]]:
        if self.fail_tags:
            return DENIED
        return OperationResult.success(self.accounts[account_id].get("Tags", []))


class FakeCostExplorer:
    """Cost Explorer double that reports ``groups`` for the first month asked and nothing for the rest."""

    def __init__(self) -> None:
        self.groups: list[tuple[str, str, str]] = []
        self.fail = False
        self.requests: list[dict[str, Any]] = []

    def get_cost_and_usage(self, time_period: dict[str, str], **kwargs: Any) -> OperationResult[list[dict[str, Any]]]:
        self.requests.append({"time_period": time_period, **kwargs})
        if self.fail:
            return DENIED
        if len(self.requests) > 1 or not self.groups:
            return OperationResult.success([])
        return OperationResult.success(
            [
                {
                    "TimePeriod": {"Start": time_period["Start"]},
                    "Groups": [
                        {"Keys": [account_id, service], "Metrics": {"UnblendedCost": {"Amount": amount, "Unit": "USD"}}}
                        for account_id, service, amount in self.groups
                    ],
                }
            ]
        )


class FakeSpreadsheet:
    """Spreadsheet provider double recording each ``update_values`` write."""

    def __init__(self) -> None:
        self.writes: list[tuple[str, str, list[list[Any]]]] = []
        self.fail = False

    def update_values(self, spreadsheet_id: str, range_name: str, values: list[list[Any]]) -> OperationResult[Any]:
        self.writes.append((spreadsheet_id, range_name, values))
        if self.fail:
            return OperationResult.error(OperationStatus.TRANSIENT_ERROR, message="quota", error_code="QUOTA")
        return OperationResult.success()


class Edges:
    def __init__(self) -> None:
        self.organizations = FakeOrganizations()
        self.cost_explorer = FakeCostExplorer()
        self.sheet = FakeSpreadsheet()


@pytest.fixture
def edges(monkeypatch: pytest.MonkeyPatch) -> Iterator[Edges]:
    """Patch the adapter builders and spreadsheet provider where the legacy module binds them, and set the sheet id."""
    fakes = Edges()
    monkeypatch.setattr(spending, "build_organizations_adapter", lambda: fakes.organizations)
    monkeypatch.setattr(spending, "build_cost_explorer_adapter", lambda: fakes.cost_explorer)
    monkeypatch.setattr(spending, "get_spreadsheet_provider", lambda: fakes.sheet)
    monkeypatch.setenv("CLOUD_OPERATIONS_SPENDING__SHEET_ID", SHEET_ID)
    get_cloud_operations_spending_settings.cache_clear()
    yield fakes
    get_cloud_operations_spending_settings.cache_clear()


def one_account_with_spend(edges: Edges) -> None:
    edges.organizations.accounts = {
        "111111111111": {
            "Name": "Forms prod",
            "Tags": [{"Key": "product", "Value": "Forms"}, {"Key": "business_unit", "Value": "Platform"}],
        }
    }
    edges.cost_explorer.groups = [("111111111111", "Amazon S3", "100.00")]


def test_accounts_and_costs_are_written_to_sheet1_with_a_header_row(edges: Edges) -> None:
    """One write replaces Sheet1 with the header row plus a row per account and service."""
    one_account_with_spend(edges)

    run_spending_job()

    assert len(edges.sheet.writes) == 1
    sheet_id, range_name, values = edges.sheet.writes[0]
    assert (sheet_id, range_name) == (SHEET_ID, "Sheet1")
    assert values[0] == HEADER
    assert len(values) == 2
    row = dict(zip(HEADER, values[1], strict=True))
    assert row["Linked account"] == "111111111111"
    assert row["Linked account name"] == "Forms prod"
    assert row["Product"] == "Forms"
    assert row["Business Unit"] == "Platform"
    assert row["Service"] == "Amazon S3"
    assert row["Cost Amount"] == 100.0
    assert row["Cost Unit"] == "USD"
    assert row["Converted Cost"] > 0


def test_each_account_and_service_pair_gets_its_own_row(edges: Edges) -> None:
    """Two accounts with two services in the reported month produce one row per pair."""
    edges.organizations.accounts = {"111111111111": {"Name": "One"}, "222222222222": {"Name": "Two"}}
    edges.cost_explorer.groups = [
        ("111111111111", "Amazon S3", "10.00"),
        ("111111111111", "AWS Lambda", "20.00"),
        ("222222222222", "Amazon S3", "30.00"),
    ]

    run_spending_job()

    rows = [dict(zip(HEADER, row, strict=True)) for row in edges.sheet.writes[0][2][1:]]
    assert sorted((row["Linked account"], row["Service"], row["Cost Amount"]) for row in rows) == [
        ("111111111111", "AWS Lambda", 20.0),
        ("111111111111", "Amazon S3", 10.0),
        ("222222222222", "Amazon S3", 30.0),
    ]


def test_twelve_months_of_costs_are_requested_grouped_by_account_and_service(edges: Edges) -> None:
    """The job asks Cost Explorer for 12 distinct monthly windows of unblended cost by linked account and service."""
    one_account_with_spend(edges)

    run_spending_job()

    assert len(edges.cost_explorer.requests) == 12
    assert len({request["time_period"]["Start"] for request in edges.cost_explorer.requests}) == 12
    assert {request["granularity"] for request in edges.cost_explorer.requests} == {"MONTHLY"}
    assert {tuple(request["metrics"]) for request in edges.cost_explorer.requests} == {("UnblendedCost",)}
    assert {tuple(group["Key"] for group in request["group_by"]) for request in edges.cost_explorer.requests} == {
        ("LINKED_ACCOUNT", "SERVICE")
    }


def test_account_without_tags_is_kept_as_unknown_product_and_business_unit(edges: Edges) -> None:
    """A failed tag lookup keeps the account in the report with Unknown tags."""
    one_account_with_spend(edges)
    edges.organizations.fail_tags = True

    run_spending_job()

    row = dict(zip(HEADER, edges.sheet.writes[0][2][1], strict=True))
    assert row["Linked account"] == "111111111111"
    assert (row["Product"], row["Business Unit"]) == ("Unknown", "Unknown")


def test_failed_account_listing_leaves_the_sheet_alone(edges: Edges) -> None:
    """A failed Organizations listing writes nothing so the old report stays."""
    one_account_with_spend(edges)
    edges.organizations.fail_listing = True

    run_spending_job()

    assert edges.sheet.writes == []


def test_failed_account_details_lookup_leaves_the_sheet_alone(edges: Edges) -> None:
    """One account that cannot be described aborts the whole report with no write."""
    one_account_with_spend(edges)
    edges.organizations.fail_details_for = {"111111111111"}

    run_spending_job()

    assert edges.sheet.writes == []


def test_failed_cost_lookup_leaves_the_sheet_alone(edges: Edges) -> None:
    """A failed Cost Explorer month aborts the report so a partial window is never written."""
    one_account_with_spend(edges)
    edges.cost_explorer.fail = True

    run_spending_job()

    assert edges.sheet.writes == []


def test_organization_without_accounts_leaves_the_sheet_alone(edges: Edges) -> None:
    """No accounts means nothing to report and no write."""
    edges.cost_explorer.groups = [("111111111111", "Amazon S3", "100.00")]

    run_spending_job()

    assert edges.sheet.writes == []


def test_window_without_spend_leaves_the_sheet_alone(edges: Edges) -> None:
    """Accounts with no cost entries in any month produce no write."""
    edges.organizations.accounts = {"111111111111": {"Name": "One"}}

    run_spending_job()

    assert edges.sheet.writes == []


def test_spend_for_an_unknown_account_is_not_written(edges: Edges) -> None:
    """Costs for an account the organization does not list are dropped, leaving nothing to write."""
    edges.organizations.accounts = {"111111111111": {"Name": "One"}}
    edges.cost_explorer.groups = [("999999999999", "Amazon S3", "50.00")]

    run_spending_job()

    assert edges.sheet.writes == []


def test_spreadsheet_write_failure_does_not_raise(edges: Edges) -> None:
    """A rejected spreadsheet write is absorbed: the job returns normally after one attempt."""
    one_account_with_spend(edges)
    edges.sheet.fail = True

    run_spending_job()

    assert len(edges.sheet.writes) == 1


def test_unset_sheet_id_skips_the_write(monkeypatch: pytest.MonkeyPatch, edges: Edges) -> None:
    """Without a configured sheet id the report is generated but not written."""
    one_account_with_spend(edges)
    monkeypatch.setenv("CLOUD_OPERATIONS_SPENDING__SHEET_ID", "")
    get_cloud_operations_spending_settings.cache_clear()

    run_spending_job()

    assert edges.sheet.writes == []
