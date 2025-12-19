"""Tests for IdentityStoreClient.

Validates AWS Identity Store operations with default identity_store_id fallback.
"""

import pytest

from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.identity_store import IdentityStoreClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestIdentityStoreClient:
    """Test suite for IdentityStoreClient."""

    def test_init_with_default_identity_store_id(self):
        """Test IdentityStoreClient initialization with default_identity_store_id."""
        session_provider = SessionProvider(region="us-east-1")
        client = IdentityStoreClient(
            session_provider=session_provider,
            default_identity_store_id="store-1234567890",
        )
        assert client._default_identity_store_id == "store-1234567890"

    def test_init_without_default_identity_store_id(self):
        """Test IdentityStoreClient initialization without default_identity_store_id."""
        session_provider = SessionProvider(region="us-east-1")
        client = IdentityStoreClient(session_provider=session_provider)
        assert client._default_identity_store_id is None

    def test_list_users_with_default_store_id(self, monkeypatch, make_fake_client):
        """Test list_users uses default identity_store_id when not provided."""

        session_provider = SessionProvider(region="us-east-1")
        client = IdentityStoreClient(
            session_provider=session_provider,
            default_identity_store_id="store-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "list_users": {
                        "Users": [{"UserId": "user-123", "UserName": "testuser"}]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_users()
        assert result.is_success

    def test_list_users_missing_store_id_returns_error(self, monkeypatch):
        """Test list_users returns error when identity_store_id is not provided."""
        session_provider = SessionProvider(region="us-east-1")
        client = IdentityStoreClient(session_provider=session_provider)

        result = client.list_users()
        assert not result.is_success
        assert result.error_code == "MISSING_IDENTITY_STORE_ID"

    def test_create_user_with_default_store_id(self, monkeypatch, make_fake_client):
        """Test create_user uses default identity_store_id."""

        session_provider = SessionProvider(region="us-east-1")
        client = IdentityStoreClient(
            session_provider=session_provider,
            default_identity_store_id="store-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={"create_user": {"UserId": "user-new-123"}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.create_user(
            UserName="newuser",
            DisplayName="New User",
        )
        assert result.is_success

    def test_describe_user_success(self, monkeypatch, make_fake_client):
        """Test describe_user returns user details."""

        session_provider = SessionProvider(region="us-east-1")
        client = IdentityStoreClient(
            session_provider=session_provider,
            default_identity_store_id="store-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "describe_user": {
                        "UserId": "user-123",
                        "UserName": "testuser",
                        "DisplayName": "Test User",
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.describe_user(user_id="user-123")
        assert result.is_success

    def test_delete_user_success(self, monkeypatch, make_fake_client):
        """Test delete_user removes a user."""

        session_provider = SessionProvider(region="us-east-1")
        client = IdentityStoreClient(
            session_provider=session_provider,
            default_identity_store_id="store-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(api_responses={"delete_user": {}})

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.delete_user(user_id="user-123")
        assert result.is_success
