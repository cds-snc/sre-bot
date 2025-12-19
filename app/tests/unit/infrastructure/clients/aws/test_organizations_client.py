"""Tests for OrganizationsClient.

Validates AWS Organizations operations with default role fallback and service_name resolution.
"""

import pytest

from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.organizations import OrganizationsClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestOrganizationsClient:
    """Test suite for OrganizationsClient."""

    def test_init_with_default_role_arn(self):
        """Test OrganizationsClient initialization with default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/OrgsRole",
        )
        assert client._default_role_arn == "arn:aws:iam::123456789012:role/OrgsRole"
        assert client._service_name == "organizations"

    def test_init_without_default_role_arn(self):
        """Test OrganizationsClient initialization without default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(session_provider=session_provider)
        assert client._default_role_arn is None

    def test_list_accounts_with_default_role(self, monkeypatch, make_fake_client):
        """Test list_accounts uses default_role_arn when not provided."""

        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::123456789012:role/DefaultRole"
            return make_fake_client(
                api_responses={
                    "list_accounts": {
                        "Accounts": [{"Id": "123456789012", "Name": "Production"}]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_accounts()
        assert result.is_success

    def test_list_accounts_explicit_role_overrides_default(
        self, monkeypatch, make_fake_client
    ):
        """Test list_accounts explicit role_arn overrides default."""

        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/DefaultRole",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            assert role_arn == "arn:aws:iam::999999999999:role/OverrideRole"
            return make_fake_client(api_responses={"list_accounts": {"Accounts": []}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_accounts(
            role_arn="arn:aws:iam::999999999999:role/OverrideRole"
        )
        assert result.is_success

    def test_describe_account_success(self, monkeypatch, make_fake_client):
        """Test describe_account returns account details."""

        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "describe_account": {
                        "Account": {"Id": "123456789012", "Name": "Production"}
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.describe_account(account_id="123456789012")
        assert result.is_success

    def test_get_account_id_by_name_success(self, monkeypatch, make_fake_client):
        """Test get_account_id_by_name finds account by name."""

        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "list_accounts": {
                        "Accounts": [
                            {"Id": "123456789012", "Name": "Production"},
                            {"Id": "999999999999", "Name": "Development"},
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_account_id_by_name("Production")
        assert result.is_success
        assert result.data["AccountId"] == "123456789012"

    def test_get_account_id_by_name_not_found(self, monkeypatch, make_fake_client):
        """Test get_account_id_by_name returns error when account not found."""

        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "list_accounts": {
                        "Accounts": [{"Id": "123456789012", "Name": "Production"}]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.get_account_id_by_name("NonExistent")
        assert not result.is_success
        assert result.error_code == "ACCOUNT_NOT_FOUND"

    def test_healthcheck_success(self, monkeypatch, make_fake_client):
        """Test healthcheck returns success for reachable Organizations."""

        session_provider = SessionProvider(region="us-east-1")
        client = OrganizationsClient(session_provider=session_provider)

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(api_responses={"list_accounts": {"Accounts": []}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.healthcheck()
        assert result.is_success
