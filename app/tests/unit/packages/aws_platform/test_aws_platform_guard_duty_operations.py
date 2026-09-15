"""Behavior tests for GuardDutyAdapter operations.

A real boto3 guardduty client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, pagination across two pages with NextToken,
and classification paths for InternalServerErrorException, BadRequestException,
ThrottlingException, BotoCoreError transient errors, and unmapped errors
propagating.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.guard_duty import GuardDutyAdapter

pytestmark = pytest.mark.unit


def _guard_duty_client() -> Any:
    """Build a real boto3 guardduty client with dummy static credentials."""
    return boto3.client(
        "guardduty",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestListDetectors:
    """ListDetectors returns paginated list of detector IDs."""

    def test_list_detectors_success_single_page(self) -> None:
        """ListDetectors with single page returns list of detector IDs."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_detectors",
                {"DetectorIds": ["detector-1", "detector-2"]},
                expected_params={},
            )

            result = adapter.list_detectors()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0] == "detector-1"
        assert result.data[1] == "detector-2"

    def test_list_detectors_pagination_two_pages(self) -> None:
        """ListDetectors flattens detector IDs across two pages via NextToken."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_detectors",
                {"DetectorIds": ["detector-1"], "NextToken": "detectors-token"},
                expected_params={},
            )
            stub.add_response(
                "list_detectors",
                {"DetectorIds": ["detector-2"]},
                expected_params={"NextToken": "detectors-token"},
            )

            result = adapter.list_detectors()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert result.data == ["detector-1", "detector-2"]

    def test_list_detectors_empty(self) -> None:
        """ListDetectors with no detectors returns empty list."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "list_detectors",
                {"DetectorIds": []},
                expected_params={},
            )

            result = adapter.list_detectors()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []


class TestGetFindingsStatistics:
    """GetFindingsStatistics returns finding counts by severity."""

    def test_get_findings_statistics_returns_count_by_severity(self) -> None:
        """GetFindingsStatistics returns CountBySeverity dict with COUNT_BY_SEVERITY statistic type."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_findings_statistics",
                {
                    "FindingStatistics": {
                        "CountBySeverity": {
                            "LOW": 5,
                            "MEDIUM": 10,
                            "HIGH": 3,
                            "CRITICAL": 1,
                        }
                    }
                },
                expected_params={
                    "DetectorId": "detector-123",
                    "FindingStatisticTypes": ["COUNT_BY_SEVERITY"],
                },
            )

            result = adapter.get_findings_statistics("detector-123")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == {
            "LOW": 5,
            "MEDIUM": 10,
            "HIGH": 3,
            "CRITICAL": 1,
        }

    def test_get_findings_statistics_with_finding_criteria(self) -> None:
        """GetFindingsStatistics sends FindingCriteria only when provided."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        finding_criteria = {"Criterion": {"severity": {"Gte": 4}}}

        with Stubber(client) as stub:
            stub.add_response(
                "get_findings_statistics",
                {"FindingStatistics": {"CountBySeverity": {"MEDIUM": 8, "HIGH": 2, "CRITICAL": 1}}},
                expected_params={
                    "DetectorId": "detector-123",
                    "FindingStatisticTypes": ["COUNT_BY_SEVERITY"],
                    "FindingCriteria": finding_criteria,
                },
            )

            result = adapter.get_findings_statistics("detector-123", finding_criteria=finding_criteria)

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == {"MEDIUM": 8, "HIGH": 2, "CRITICAL": 1}

    def test_get_findings_statistics_empty_returns_empty_dict(self) -> None:
        """GetFindingsStatistics with no statistics returns empty dict."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "get_findings_statistics",
                {"FindingStatistics": {}},
                expected_params={
                    "DetectorId": "detector-123",
                    "FindingStatisticTypes": ["COUNT_BY_SEVERITY"],
                },
            )

            result = adapter.get_findings_statistics("detector-123")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == {}


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_detectors",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.list_detectors()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_internal_server_error_classification(self) -> None:
        """InternalServerErrorException maps to TRANSIENT_ERROR."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_findings_statistics",
                service_error_code="InternalServerErrorException",
                http_status_code=500,
            )

            result = adapter.get_findings_statistics("detector-123")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "InternalServerErrorException"

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:

            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://guardduty.ca-central-1.amazonaws.com")

            stub.client.list_detectors = raise_endpoint_error

            result = adapter.list_detectors()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_findings_statistics",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.get_findings_statistics("detector-123")

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_bad_request_exception_propagates(self) -> None:
        """BadRequestException (unmapped) propagates as ClientError."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_detectors",
                service_error_code="BadRequestException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.list_detectors()

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "BadRequestException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _guard_duty_client()
        adapter = GuardDutyAdapter(client=client)

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.list_detectors = raise_key_error

            with pytest.raises(KeyError):
                adapter.list_detectors()

            stub.assert_no_pending_responses()
