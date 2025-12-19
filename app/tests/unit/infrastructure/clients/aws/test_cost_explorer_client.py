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
        assert client.service_name == "ce"

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

    def test_get_cost_and_usage_with_filters(self, monkeypatch, make_fake_client):
        """Test get_cost_and_usage with filter parameters."""

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
                api_responses={"get_cost_and_usage": {"ResultsByTime": []}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_cost_and_usage(
            time_period={"Start": "2024-01-01", "End": "2024-01-02"},
            granularity="MONTHLY",
            metrics=["BlendedCost"],
            Filter={"Dimensions": {"Key": "REGION", "Values": ["us-east-1"]}},
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
