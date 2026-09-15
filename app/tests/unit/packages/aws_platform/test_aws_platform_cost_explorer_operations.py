"""Behavior tests for CostExplorerAdapter operations.

A real boto3 cost-explorer client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, manual pagination across two pages with
NextPageToken (since GetCostAndUsage has no boto3 paginator), and classification
paths for LimitExceededException, DataUnavailableException, BotoCoreError
transient errors, and unmapped errors propagating. The adapter reduces the full
response to the concatenated ResultsByTime list.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.cost_explorer import CostExplorerAdapter

pytestmark = pytest.mark.unit


def _cost_explorer_client() -> Any:
    """Build a real boto3 cost-explorer client with dummy static credentials."""
    return boto3.client(
        "ce",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestGetCostAndUsage:
    """GetCostAndUsage returns concatenated list of ResultsByTime from all pages."""

    def test_get_cost_and_usage_single_page(self) -> None:
        """GetCostAndUsage with single page returns concatenated ResultsByTime."""
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_cost_and_usage",
                {
                    "ResultsByTime": [
                        {
                            "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                            "Total": {"UnblendedCost": {"Amount": "100", "Unit": "USD"}},
                            "Estimated": False,
                        }
                    ]
                },
                expected_params={
                    "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                    "Granularity": "MONTHLY",
                    "Metrics": ["UnblendedCost"],
                },
            )

            result = adapter.get_cost_and_usage(
                time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                granularity="MONTHLY",
                metrics=["UnblendedCost"],
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["TimePeriod"]["Start"] == "2023-01-01"

    def test_get_cost_and_usage_follows_next_page_token(self) -> None:
        """GetCostAndUsage manually paginates via NextPageToken, returning concatenated ResultsByTime.

        This test verifies the pagination fix: Cost Explorer has no boto3 paginator,
        so the adapter implements manual NextPageToken handling to avoid silent truncation.
        The second request echoes the same params plus the NextPageToken from the first response.
        """
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_cost_and_usage",
                {
                    "ResultsByTime": [
                        {
                            "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                            "Total": {"UnblendedCost": {"Amount": "100", "Unit": "USD"}},
                            "Estimated": False,
                        }
                    ],
                    "NextPageToken": "cost-token",
                },
                expected_params={
                    "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                    "Granularity": "MONTHLY",
                    "Metrics": ["UnblendedCost"],
                },
            )
            stub.add_response(
                "get_cost_and_usage",
                {
                    "ResultsByTime": [
                        {
                            "TimePeriod": {"Start": "2023-02-01", "End": "2023-02-28"},
                            "Total": {"UnblendedCost": {"Amount": "200", "Unit": "USD"}},
                            "Estimated": False,
                        }
                    ]
                },
                expected_params={
                    "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                    "Granularity": "MONTHLY",
                    "Metrics": ["UnblendedCost"],
                    "NextPageToken": "cost-token",
                },
            )

            result = adapter.get_cost_and_usage(
                time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                granularity="MONTHLY",
                metrics=["UnblendedCost"],
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [r["TimePeriod"]["Start"] for r in result.data] == ["2023-01-01", "2023-02-01"]

    def test_get_cost_and_usage_sends_filter_and_group_by_only_when_given(self) -> None:
        """GetCostAndUsage sends Filter and GroupBy only when provided, omits when None.

        Omitting these keys avoids unnecessary param validation.
        """
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        # Test with filter and group_by
        with Stubber(client) as stub:
            stub.add_response(
                "get_cost_and_usage",
                {
                    "ResultsByTime": [
                        {
                            "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                            "Total": {"UnblendedCost": {"Amount": "100", "Unit": "USD"}},
                            "Groups": [
                                {
                                    "Keys": ["Amazon S3"],
                                    "Metrics": {"UnblendedCost": {"Amount": "50", "Unit": "USD"}},
                                }
                            ],
                            "Estimated": False,
                        }
                    ]
                },
                expected_params={
                    "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                    "Granularity": "MONTHLY",
                    "Metrics": ["UnblendedCost"],
                    "Filter": {"Dimensions": {"Key": "SERVICE", "Values": ["Amazon S3"]}},
                    "GroupBy": [{"Type": "DIMENSION", "Key": "SERVICE"}],
                },
            )

            result = adapter.get_cost_and_usage(
                time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                granularity="MONTHLY",
                metrics=["UnblendedCost"],
                filter_expression={"Dimensions": {"Key": "SERVICE", "Values": ["Amazon S3"]}},
                group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}],
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1

        # Test without filter and group_by (should omit the keys)
        with Stubber(client) as stub:
            stub.add_response(
                "get_cost_and_usage",
                {
                    "ResultsByTime": [
                        {
                            "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                            "Total": {"UnblendedCost": {"Amount": "100", "Unit": "USD"}},
                            "Estimated": False,
                        }
                    ]
                },
                expected_params={
                    "TimePeriod": {"Start": "2023-01-01", "End": "2023-01-31"},
                    "Granularity": "MONTHLY",
                    "Metrics": ["UnblendedCost"],
                },
            )

            result = adapter.get_cost_and_usage(
                time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                granularity="MONTHLY",
                metrics=["UnblendedCost"],
                filter_expression=None,
                group_by=None,
            )

            stub.assert_no_pending_responses()

        assert result.is_success


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_limit_exceeded_is_transient(self) -> None:
        """LimitExceededException maps to TRANSIENT_ERROR."""
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_cost_and_usage",
                service_error_code="LimitExceededException",
                http_status_code=400,
            )

            result = adapter.get_cost_and_usage(
                time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                granularity="MONTHLY",
                metrics=["UnblendedCost"],
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "LimitExceededException"

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_cost_and_usage",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.get_cost_and_usage(
                time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                granularity="MONTHLY",
                metrics=["UnblendedCost"],
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:

            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://ce.ca-central-1.amazonaws.com")

            stub.client.get_cost_and_usage = raise_endpoint_error

            result = adapter.get_cost_and_usage(
                time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                granularity="MONTHLY",
                metrics=["UnblendedCost"],
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_data_unavailable_propagates(self) -> None:
        """DataUnavailableException (unmapped) propagates as ClientError.

        This is a programmer/input error: the service rejects the requested date range
        as not yet available, which the caller must handle.
        """
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_cost_and_usage",
                service_error_code="DataUnavailableException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.get_cost_and_usage(
                    time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                    granularity="MONTHLY",
                    metrics=["UnblendedCost"],
                )

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "DataUnavailableException"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_cost_and_usage",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.get_cost_and_usage(
                    time_period={"Start": "invalid", "End": "invalid"},
                    granularity="MONTHLY",
                    metrics=["UnblendedCost"],
                )

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _cost_explorer_client()
        adapter = CostExplorerAdapter(client=client)

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.get_cost_and_usage = raise_key_error

            with pytest.raises(KeyError):
                adapter.get_cost_and_usage(
                    time_period={"Start": "2023-01-01", "End": "2023-01-31"},
                    granularity="MONTHLY",
                    metrics=["UnblendedCost"],
                )

            stub.assert_no_pending_responses()
