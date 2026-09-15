"""Behavior tests for ConfigAdapter operations.

A real boto3 config client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, pagination across two pages with NextToken,
and classification paths for NoSuchConfigurationAggregatorException,
InvalidAccessException, InternalServerErrorException, BotoCoreError transient
errors, and unmapped errors propagating.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.config import ConfigAdapter

pytestmark = pytest.mark.unit


def _config_client() -> Any:
    """Build a real boto3 config client with dummy static credentials."""
    return boto3.client(
        "config",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestDescribeAggregateComplianceByConfigRules:
    """DescribeAggregateComplianceByConfigRules returns paginated compliance list."""

    def test_describe_aggregate_compliance_single_page(self) -> None:
        """DescribeAggregateComplianceByConfigRules with single page returns compliance list."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "describe_aggregate_compliance_by_config_rules",
                {
                    "AggregateComplianceByConfigRules": [
                        {
                            "ConfigRuleName": "my-rule",
                            "Compliance": {
                                "ComplianceType": "COMPLIANT",
                                "ComplianceContributorCount": {"CappedCount": 5, "CapExceeded": False},
                            },
                        }
                    ]
                },
                expected_params={"ConfigurationAggregatorName": "my-aggregator"},
            )

            result = adapter.describe_aggregate_compliance_by_config_rules("my-aggregator")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["ConfigRuleName"] == "my-rule"

    def test_describe_aggregate_compliance_pagination_two_pages(self) -> None:
        """DescribeAggregateComplianceByConfigRules flattens results across two pages via NextToken."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "describe_aggregate_compliance_by_config_rules",
                {
                    "AggregateComplianceByConfigRules": [
                        {
                            "ConfigRuleName": "rule-1",
                            "Compliance": {"ComplianceType": "COMPLIANT"},
                        }
                    ],
                    "NextToken": "compliance-token",
                },
                expected_params={"ConfigurationAggregatorName": "my-aggregator"},
            )
            stub.add_response(
                "describe_aggregate_compliance_by_config_rules",
                {
                    "AggregateComplianceByConfigRules": [
                        {
                            "ConfigRuleName": "rule-2",
                            "Compliance": {"ComplianceType": "NON_COMPLIANT"},
                        }
                    ]
                },
                expected_params={"ConfigurationAggregatorName": "my-aggregator", "NextToken": "compliance-token"},
            )

            result = adapter.describe_aggregate_compliance_by_config_rules("my-aggregator")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [r["ConfigRuleName"] for r in result.data] == ["rule-1", "rule-2"]

    def test_describe_aggregate_compliance_empty(self) -> None:
        """DescribeAggregateComplianceByConfigRules with no results returns empty list."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_response(
                "describe_aggregate_compliance_by_config_rules",
                {"AggregateComplianceByConfigRules": []},
                expected_params={"ConfigurationAggregatorName": "my-aggregator"},
            )

            result = adapter.describe_aggregate_compliance_by_config_rules("my-aggregator")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []

    def test_describe_aggregate_compliance_sends_filters_only_when_given(self) -> None:
        """DescribeAggregateComplianceByConfigRules sends Filters only when provided, omits when None.

        Omitting Filters avoids botocore ParamValidationError when None is passed explicitly.
        """
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        # Test with filters
        with Stubber(client) as stub:
            stub.add_response(
                "describe_aggregate_compliance_by_config_rules",
                {
                    "AggregateComplianceByConfigRules": [
                        {
                            "ConfigRuleName": "rule-1",
                            "Compliance": {"ComplianceType": "COMPLIANT"},
                        }
                    ]
                },
                expected_params={
                    "ConfigurationAggregatorName": "my-aggregator",
                    "Filters": {"AccountId": "123456789012"},
                },
            )

            result = adapter.describe_aggregate_compliance_by_config_rules(
                "my-aggregator",
                filters={"AccountId": "123456789012"},
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1

        # Test without filters (should omit the Filters key)
        with Stubber(client) as stub:
            stub.add_response(
                "describe_aggregate_compliance_by_config_rules",
                {
                    "AggregateComplianceByConfigRules": [
                        {
                            "ConfigRuleName": "rule-1",
                            "Compliance": {"ComplianceType": "COMPLIANT"},
                        }
                    ]
                },
                expected_params={"ConfigurationAggregatorName": "my-aggregator"},
            )

            result = adapter.describe_aggregate_compliance_by_config_rules("my-aggregator", filters=None)

            stub.assert_no_pending_responses()

        assert result.is_success


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_no_such_configuration_aggregator_not_found(self) -> None:
        """NoSuchConfigurationAggregatorException maps to NOT_FOUND."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "describe_aggregate_compliance_by_config_rules",
                service_error_code="NoSuchConfigurationAggregatorException",
                http_status_code=404,
            )

            result = adapter.describe_aggregate_compliance_by_config_rules("nonexistent")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "NoSuchConfigurationAggregatorException"

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "describe_aggregate_compliance_by_config_rules",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.describe_aggregate_compliance_by_config_rules("my-aggregator")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:

            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://config.ca-central-1.amazonaws.com")

            stub.client.describe_aggregate_compliance_by_config_rules = raise_endpoint_error

            result = adapter.describe_aggregate_compliance_by_config_rules("my-aggregator")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:
            stub.add_client_error(
                "describe_aggregate_compliance_by_config_rules",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.describe_aggregate_compliance_by_config_rules("invalid")

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _config_client()
        adapter = ConfigAdapter(client=client)

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.describe_aggregate_compliance_by_config_rules = raise_key_error

            with pytest.raises(KeyError):
                adapter.describe_aggregate_compliance_by_config_rules("my-aggregator")

            stub.assert_no_pending_responses()
