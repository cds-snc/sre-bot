"""Tests for CostExplorerClient.

Validates AWS Cost Explorer operations with default role fallback and service_name resolution.
"""

import pytest

from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.cost_explorer import CostExplorerClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestCostExplorerClient:
    """Test suite for CostExplorerClient."""

    def test_init_with_default_role_arn(self):
        """Test CostExplorerClient initialization with default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/CostExplorerRole",
        )
        assert (
            client._default_role_arn
            == "arn:aws:iam::123456789012:role/CostExplorerRole"
        )
        assert client._service_name == "ce"

    def test_init_without_default_role_arn(self):
        """Test CostExplorerClient initialization without default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(session_provider=session_provider)
        assert client._default_role_arn is None

    def test_get_cost_and_usage_with_default_role(self, monkeypatch, make_fake_client):
        """Test get_cost_and_usage uses default_role_arn when not provided."""

        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::123456789012:role/DefaultRole"
            return make_fake_client(
                api_responses={
                    "get_cost_and_usage": {
                        "ResultsByTime": [
                            {
                                "TimePeriod": {
                                    "Start": "2024-01-01",
                                    "End": "2024-01-02",
                                },
                                "Total": {
                                    "BlendedCost": {"Amount": "100", "Unit": "USD"}
                                },
                            }
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_cost_and_usage(
            time_period={"Start": "2024-01-01", "End": "2024-01-02"},
            granularity="MONTHLY",
            metrics=["BlendedCost"],
        )
        assert result.is_success

    def test_get_cost_and_usage_explicit_role_overrides_default(
        self, monkeypatch, make_fake_client
    ):
        """Test get_cost_and_usage explicit role_arn overrides default."""

        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::999999999999:role/OverrideRole"
            return make_fake_client(
                api_responses={"get_cost_and_usage": {"ResultsByTime": []}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_cost_and_usage(
            time_period={"Start": "2024-01-01", "End": "2024-01-02"},
            granularity="MONTHLY",
            metrics=["BlendedCost"],
            role_arn="arn:aws:iam::999999999999:role/OverrideRole",
        )
        assert result.is_success

    def test_get_cost_and_usage_success(self, monkeypatch, make_fake_client):
        """Test get_cost_and_usage returns cost data."""

        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "get_cost_and_usage": {
                        "ResultsByTime": [
                            {
                                "TimePeriod": {
                                    "Start": "2024-01-01",
                                    "End": "2024-01-02",
                                },
                                "Total": {
                                    "BlendedCost": {"Amount": "100", "Unit": "USD"}
                                },
                            }
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_cost_and_usage(
            time_period={"Start": "2024-01-01", "End": "2024-01-02"},
            granularity="MONTHLY",
            metrics=["BlendedCost"],
        )
        assert result.is_success

    def test_get_dimension_values_success(self, monkeypatch, make_fake_client):
        """Test get_dimension_values returns dimension values."""

        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "get_dimension_values": {
                        "DimensionValues": ["us-east-1", "us-west-2"]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_dimension_values(
            time_period={"Start": "2024-01-01", "End": "2024-01-02"},
            dimension="REGION",
        )
        assert result.is_success

    def test_get_reservation_utilization_success(self, monkeypatch, make_fake_client):
        """Test get_reservation_utilization returns reservation data."""

        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "get_reservation_utilization": {
                        "UtilizationsByTime": [
                            {
                                "TimePeriod": {
                                    "Start": "2024-01-01",
                                    "End": "2024-01-02",
                                },
                                "Total": {"UtilizationPercentage": "80"},
                            }
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_reservation_utilization(
            time_period={"Start": "2024-01-01", "End": "2024-01-02"}
        )
        assert result.is_success

    def test_healthcheck_success(self, monkeypatch, make_fake_client):
        """Test healthcheck returns success for reachable Cost Explorer."""

        session_provider = SessionProvider(region="us-east-1")
        client = CostExplorerClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={"get_dimension_values": {"DimensionValues": []}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.healthcheck()
        assert result.is_success
