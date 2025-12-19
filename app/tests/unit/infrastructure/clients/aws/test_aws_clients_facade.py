"""Tests for AWSClients facade.

Validates AWS clients composition, default configuration, and service integration.
"""

import pytest

from infrastructure.clients.aws import (
    AWSClients,
    DynamoDBClient,
    IdentityStoreClient,
    OrganizationsClient,
    SsoAdminClient,
    ConfigClient,
    GuardDutyClient,
    CostExplorerClient,
)


@pytest.mark.unit
class TestAWSClientsFacade:
    """Test suite for AWSClients facade."""

    def test_facade_initialization_with_settings(self, mock_aws_settings):
        """Test AWSClients initializes all service clients from AwsSettings."""
        clients = AWSClients(aws_settings=mock_aws_settings)

        assert isinstance(clients.dynamodb, DynamoDBClient)
        assert isinstance(clients.identitystore, IdentityStoreClient)
        assert isinstance(clients.organizations, OrganizationsClient)
        assert isinstance(clients.sso_admin, SsoAdminClient)
        assert isinstance(clients.config, ConfigClient)
        assert isinstance(clients.guardduty, GuardDutyClient)
        assert isinstance(clients.cost_explorer, CostExplorerClient)

    def test_facade_creates_session_provider(self, mock_aws_settings):
        """Test AWSClients creates SessionProvider with correct settings."""
        clients = AWSClients(aws_settings=mock_aws_settings)

        assert clients._session_provider is not None
        assert clients._session_provider.region == mock_aws_settings.AWS_REGION

    def test_facade_passes_default_role_arn_to_dynamodb_client(self, mock_aws_settings):
        """Test AWSClients passes correct default_role_arn to DynamoDBClient."""
        mock_aws_settings.SERVICE_ROLE_MAP = {
            "dynamodb": "arn:aws:iam::123456789012:role/DynamoDBRole",
        }

        clients = AWSClients(aws_settings=mock_aws_settings)

        assert (
            clients.dynamodb._default_role_arn
            == "arn:aws:iam::123456789012:role/DynamoDBRole"
        )

    def test_facade_passes_default_role_arn_to_organizations_client(
        self, mock_aws_settings
    ):
        """Test AWSClients passes correct default_role_arn to OrganizationsClient."""
        mock_aws_settings.SERVICE_ROLE_MAP = {
            "organizations": "arn:aws:iam::123456789012:role/OrganizationsRole",
        }

        clients = AWSClients(aws_settings=mock_aws_settings)

        assert (
            clients.organizations._default_role_arn
            == "arn:aws:iam::123456789012:role/OrganizationsRole"
        )

    def test_facade_passes_default_sso_instance_arn_to_sso_admin(
        self, mock_aws_settings
    ):
        """Test AWSClients passes INSTANCE_ARN to SsoAdminClient."""
        mock_aws_settings.INSTANCE_ARN = "arn:aws:sso:::instance/sso-1234567890"

        clients = AWSClients(aws_settings=mock_aws_settings)

        assert (
            clients.sso_admin._default_sso_instance_arn
            == "arn:aws:sso:::instance/sso-1234567890"
        )

    def test_facade_passes_identity_store_id_to_identity_store(self, mock_aws_settings):
        """Test AWSClients passes INSTANCE_ID to IdentityStoreClient."""
        mock_aws_settings.INSTANCE_ID = "d-1234567890"

        clients = AWSClients(aws_settings=mock_aws_settings)

        assert clients.identitystore._default_identity_store_id == "d-1234567890"

    def test_facade_all_clients_have_session_provider(self, mock_aws_settings):
        """Test all service clients receive the same SessionProvider instance."""
        clients = AWSClients(aws_settings=mock_aws_settings)

        assert clients.dynamodb._session_provider is clients._session_provider
        assert clients.identitystore._session_provider is clients._session_provider
        assert clients.organizations._session_provider is clients._session_provider
        assert clients.sso_admin._session_provider is clients._session_provider
        assert clients.config._session_provider is clients._session_provider
        assert clients.guardduty._session_provider is clients._session_provider
        assert clients.cost_explorer._session_provider is clients._session_provider

    def test_facade_service_name_resolution(self, mock_aws_settings):
        """Test AWSClients resolves service names correctly for role lookup."""
        mock_aws_settings.SERVICE_ROLE_MAP = {
            "dynamodb": "arn:aws:iam::123456789012:role/DynamoDBRole",
            "organizations": "arn:aws:iam::123456789012:role/OrganizationsRole",
        }

        clients = AWSClients(aws_settings=mock_aws_settings)

        # DynamoDB service_name is "dynamodb"
        assert clients.dynamodb._service_name == "dynamodb"
        # Organizations service_name is "organizations"
        assert clients.organizations._service_name == "organizations"

    def test_facade_with_empty_service_role_map(self, mock_aws_settings):
        """Test AWSClients handles empty SERVICE_ROLE_MAP gracefully."""
        mock_aws_settings.SERVICE_ROLE_MAP = {}

        clients = AWSClients(aws_settings=mock_aws_settings)

        # Clients should initialize without default role ARNs
        assert clients.dynamodb._default_role_arn is None
        assert clients.organizations._default_role_arn is None

    def test_facade_endpoint_url_configuration(self, mock_aws_settings):
        """Test AWSClients passes endpoint_url configuration to SessionProvider."""
        mock_aws_settings.ENDPOINT_URL = "https://dynamodb.example.com"

        clients = AWSClients(aws_settings=mock_aws_settings)

        # SessionProvider should have endpoint_url set
        assert clients._session_provider.endpoint_url == "https://dynamodb.example.com"

    def test_facade_region_configuration(self, mock_aws_settings):
        """Test AWSClients passes region configuration to SessionProvider."""
        mock_aws_settings.AWS_REGION = "eu-west-1"

        clients = AWSClients(aws_settings=mock_aws_settings)

        # SessionProvider should have correct region
        assert clients._session_provider.region == "eu-west-1"

    def test_facade_idempotent_initialization(self, mock_aws_settings):
        """Test creating multiple facade instances independently."""
        clients1 = AWSClients(aws_settings=mock_aws_settings)
        clients2 = AWSClients(aws_settings=mock_aws_settings)

        # Should create independent instances
        assert clients1 is not clients2
        # But all clients should be functional
        assert isinstance(clients1.dynamodb, DynamoDBClient)
        assert isinstance(clients2.dynamodb, DynamoDBClient)

    def test_facade_has_health_aggregator(self, mock_aws_settings):
        """Test AWSClients has health attribute for health checks."""
        clients = AWSClients(aws_settings=mock_aws_settings)

        assert hasattr(clients, "health")
        assert clients.health is not None
