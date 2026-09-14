"""Behavior tests for SecurityHubAdapter operations.

A real boto3 securityhub client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, pagination across two pages with NextToken,
and classification paths for InvalidAccessException, ThrottlingException,
BotoCoreError transient errors, and unmapped errors propagating.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.security_hub import SecurityHubAdapter

pytestmark = pytest.mark.unit


def _security_hub_client() -> Any:
    """Build a real boto3 securityhub client with dummy static credentials."""
    return boto3.client(
        "securityhub",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestGetFindings:
    """GetFindings returns paginated flat list of findings."""

    def test_get_findings_success_single_page(self) -> None:
        """GetFindings with single page returns flat list of finding dicts."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_findings",
                {
                    "Findings": [
                        {
                            "AwsAccountId": "123456789012",
                            "Id": "finding-1",
                            "Type": "Software and Configuration Checks",
                            "Severity": {"Label": "MEDIUM"},
                        }
                    ]
                },
                expected_params={"Filters": {}},
            )

            result = adapter.get_findings({})

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["Id"] == "finding-1"
        assert result.data[0]["Severity"]["Label"] == "MEDIUM"

    def test_get_findings_pagination_two_pages_returns_flat_findings(self) -> None:
        """GetFindings flattens findings across two pages via NextToken and returns no NextToken in result.

        This test verifies the bug fix: the legacy mirror's unkeyed paginator flattened
        every field including NextToken into the result, corrupting the shape. The
        adapter's _paginate helper with explicit response_key='Findings' returns only
        the findings, with NextToken properly filtered out.
        """
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_findings",
                {
                    "Findings": [
                        {"Id": "finding-1", "Severity": {"Label": "LOW"}},
                    ],
                    "NextToken": "findings-token",
                },
                expected_params={"Filters": {}},
            )
            stub.add_response(
                "get_findings",
                {
                    "Findings": [
                        {"Id": "finding-2", "Severity": {"Label": "HIGH"}},
                    ]
                },
                expected_params={"Filters": {}, "NextToken": "findings-token"},
            )

            result = adapter.get_findings({})

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [f["Id"] for f in result.data] == ["finding-1", "finding-2"]
        # Ensure NextToken is not leaked into the result
        for finding in result.data:
            assert "NextToken" not in finding

    def test_get_findings_empty(self) -> None:
        """GetFindings with no findings returns empty list."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_findings",
                {"Findings": []},
                expected_params={"Filters": {}},
            )

            result = adapter.get_findings({})

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []

    def test_get_findings_with_filters(self) -> None:
        """GetFindings sends filters as Filters parameter."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        filters = {
            "SeverityLabel": [
                {"Value": "HIGH", "Comparison": "EQUALS"},
                {"Value": "CRITICAL", "Comparison": "EQUALS"},
            ]
        }

        with Stubber(client) as stub:
            stub.add_response(
                "get_findings",
                {
                    "Findings": [
                        {"Id": "finding-1", "Severity": {"Label": "HIGH"}},
                        {"Id": "finding-2", "Severity": {"Label": "CRITICAL"}},
                    ]
                },
                expected_params={"Filters": filters},
            )

            result = adapter.get_findings(filters)

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_invalid_access_exception_classification(self) -> None:
        """InvalidAccessException maps to UNAUTHORIZED."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_findings",
                service_error_code="InvalidAccessException",
                http_status_code=403,
            )

            result = adapter.get_findings({})

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == "InvalidAccessException"

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_findings",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.get_findings({})

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:

            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://securityhub.ca-central-1.amazonaws.com")

            stub.client.get_findings = raise_endpoint_error

            result = adapter.get_findings({})

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_findings",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.get_findings({})

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _security_hub_client()
        adapter = SecurityHubAdapter(client=client)

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.get_findings = raise_key_error

            with pytest.raises(KeyError):
                adapter.get_findings({})

            stub.assert_no_pending_responses()
