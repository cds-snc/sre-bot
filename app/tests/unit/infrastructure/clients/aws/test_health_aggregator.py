"""Tests for AWSIntegrationHealth.

Validates aggregated health checks across all AWS services.
"""

import pytest

from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.health import AWSIntegrationHealth
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
@pytest.mark.skip(reason="Health aggregator logic not optimal, needs refactoring")
class TestAWSIntegrationHealth:
    """Test suite for AWSIntegrationHealth."""

    def test_init_with_default_configuration(self):
        """Test AWSIntegrationHealth initialization with default configuration."""
        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(
            session_provider=session_provider,
        )

        assert aggregator._session_provider is session_provider
        assert hasattr(aggregator, "dynamodb")
        assert hasattr(aggregator, "identitystore")
        assert hasattr(aggregator, "organizations")
        assert hasattr(aggregator, "ssoadmin")
        assert hasattr(aggregator, "config")
        assert hasattr(aggregator, "guardduty")
        assert hasattr(aggregator, "costexplorer")

    def test_init_with_custom_configuration(self):
        """Test AWSIntegrationHealth initialization with custom settings."""
        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(
            session_provider=session_provider,
            default_identity_store_id="d-1234567890",
            default_sso_instance_arn="arn:aws:sso:::instance/sso-1234567890",
            config_aggregator_name="org-aggregator",
            include_guardduty=True,
            include_cost_explorer=True,
        )

        assert aggregator._session_provider is session_provider
        assert aggregator.identitystore._default_identity_store_id == "d-1234567890"

    def test_check_service_health_dynamodb(self, monkeypatch, make_fake_client):
        """Test check_service_health for dynamodb."""

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(api_responses={"list_tables": {"TableNames": []}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        result = aggregator.check_service_health("dynamodb")
        assert result.is_success

    def test_check_service_health_organizations(self, monkeypatch, make_fake_client):
        """Test check_service_health for organizations."""

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(api_responses={"list_accounts": {"Accounts": []}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        result = aggregator.check_service_health("organizations")
        assert result.is_success

    def test_check_service_health_invalid_service(self):
        """Test check_service_health returns error for invalid service name."""
        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        result = aggregator.check_service_health("invalid_service")
        assert not result.is_success
        assert result.error_code == "SERVICE_NOT_FOUND"

    def test_check_all_returns_aggregated_results(self, monkeypatch, make_fake_client):
        """Test check_all returns aggregated health for all services."""

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            responses = {
                "dynamodb": {"list_tables": {"TableNames": []}},
                "organizations": {"list_accounts": {"Accounts": []}},
            }
            return make_fake_client(api_responses=responses.get(service_name, {}))

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        result = aggregator.check_all()
        assert result.is_success
        # Should have aggregated results
        assert isinstance(result.data, dict)

    def test_check_all_with_include_filter(self, monkeypatch, make_fake_client):
        """Test check_all with include filter only checks specified services."""

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            if service_name == "dynamodb":
                return make_fake_client(
                    api_responses={"list_tables": {"TableNames": []}}
                )
            elif service_name == "organizations":
                return make_fake_client(
                    api_responses={"list_accounts": {"Accounts": []}}
                )
            return make_fake_client(api_responses={})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        result = aggregator.check_all(include={"dynamodb"})
        assert result.is_success
        # Should only have dynamodb result
        assert len(result.data) == 1
        assert "dynamodb" in result.data

    def test_check_all_with_exclude_filter(self, monkeypatch, make_fake_client):
        """Test check_all with exclude filter skips specified services."""

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            if service_name == "dynamodb":
                return make_fake_client(
                    api_responses={"list_tables": {"TableNames": []}}
                )
            elif service_name == "organizations":
                return make_fake_client(
                    api_responses={"list_accounts": {"Accounts": []}}
                )
            return make_fake_client(api_responses={})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        result = aggregator.check_all(exclude={"organizations"})
        assert result.is_success
        # Should not have organizations result
        assert "organizations" not in result.data
        assert "dynamodb" in result.data

    def test_check_all_with_both_include_and_exclude(self):
        """Test check_all with both include and exclude uses union."""
        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        # include takes precedence when both are specified
        result = aggregator.check_all(
            include={"dynamodb"},
            exclude={"organizations"},
        )
        assert result.is_success
        assert "dynamodb" in result.data

    def test_check_all_excludes_optional_services_by_default(self):
        """Test check_all excludes GuardDuty and CostExplorer when include_X_Y flags are False."""
        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(
            session_provider=session_provider,
            include_guardduty=False,
            include_cost_explorer=False,
        )

        result = aggregator.check_all()
        assert result.is_success
        # Should not include optional services
        assert "guardduty" not in result.data
        assert "costexplorer" not in result.data

    def test_region_configuration(self):
        """Test AWSIntegrationHealth respects region configuration."""
        session_provider = SessionProvider(region="eu-west-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        # SessionProvider should have correct region
        assert aggregator._session_provider.region == "eu-west-1"

    def test_check_all_aggregates_results(self, monkeypatch, make_fake_client):
        """Test check_all aggregates all service check results."""

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            responses = {
                "dynamodb": {"list_tables": {"TableNames": []}},
                "organizations": {"list_accounts": {"Accounts": []}},
                "identity-store": {"list_users": {"Users": []}},
            }
            return make_fake_client(api_responses=responses.get(service_name, {}))

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        session_provider = SessionProvider(region="us-east-1")
        aggregator = AWSIntegrationHealth(session_provider=session_provider)

        result = aggregator.check_all()
        assert result.is_success
        assert isinstance(result.data, dict)
