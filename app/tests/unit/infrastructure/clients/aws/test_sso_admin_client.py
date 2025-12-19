"""Tests for SsoAdminClient.

Validates AWS SSO Admin operations with default SSO instance ARN and service_name resolution.
"""

import pytest

from infrastructure.clients.aws import executor as aws_client
from infrastructure.clients.aws.sso_admin import SsoAdminClient
from infrastructure.clients.aws.session_provider import SessionProvider


@pytest.mark.unit
class TestSsoAdminClient:
    """Test suite for SsoAdminClient."""

    def test_init_with_default_sso_instance_arn(self):
        """Test SsoAdminClient initialization with default_sso_instance_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_sso_instance_arn="arn:aws:sso:::instance/sso-1234567890",
        )
        assert (
            client._default_sso_instance_arn == "arn:aws:sso:::instance/sso-1234567890"
        )
        assert client._service_name == "sso-admin"

    def test_init_without_default_sso_instance_arn(self):
        """Test SsoAdminClient initialization without default_sso_instance_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(session_provider=session_provider)
        assert client._default_sso_instance_arn is None

    def test_init_with_default_role_arn(self):
        """Test SsoAdminClient initialization with default_role_arn."""
        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_role_arn="arn:aws:iam::123456789012:role/SSORole",
        )
        assert client._default_role_arn == "arn:aws:iam::123456789012:role/SSORole"

    def test_create_account_assignment_success(self, monkeypatch, make_fake_client):
        """Test create_account_assignment returns request ID."""

        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_sso_instance_arn="arn:aws:sso:::instance/sso-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "create_account_assignment": {
                        "AccountAssignmentCreationStatus": {"RequestId": "req-12345"}
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.create_account_assignment(
            instance_arn="arn:aws:sso:::instance/sso-1234567890",
            target_id="123456789012",
            target_type="AWS_ACCOUNT",
            permission_set_arn="arn:aws:sso:::permissionSet/ps-1234567890",
            principal_type="USER",
            principal_id="user-123",
        )
        assert result.is_success

    def test_create_account_assignment_uses_default_instance_arn(
        self, monkeypatch, make_fake_client
    ):
        """Test create_account_assignment uses default_sso_instance_arn when not provided."""

        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_sso_instance_arn="arn:aws:sso:::instance/sso-default",
        )

        call_count = 0

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            nonlocal call_count
            call_count += 1
            fake_client = make_fake_client(
                api_responses={
                    "create_account_assignment": {
                        "AccountAssignmentCreationStatus": {"RequestId": "req-12345"}
                    }
                }
            )
            # Store the first call's instance_arn for validation
            return fake_client

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.create_account_assignment(
            target_id="123456789012",
            target_type="AWS_ACCOUNT",
            permission_set_arn="arn:aws:sso:::permissionSet/ps-1234567890",
            principal_type="USER",
            principal_id="user-123",
        )
        assert result.is_success
        assert call_count == 1

    def test_delete_account_assignment_success(self, monkeypatch, make_fake_client):
        """Test delete_account_assignment returns request ID."""

        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_sso_instance_arn="arn:aws:sso:::instance/sso-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "delete_account_assignment": {
                        "AccountAssignmentDeletionStatus": {"RequestId": "req-12345"}
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.delete_account_assignment(
            instance_arn="arn:aws:sso:::instance/sso-1234567890",
            target_id="123456789012",
            target_type="AWS_ACCOUNT",
            permission_set_arn="arn:aws:sso:::permissionSet/ps-1234567890",
            principal_type="USER",
            principal_id="user-123",
        )
        assert result.is_success

    def test_list_account_assignments_success(self, monkeypatch, make_fake_client):
        """Test list_account_assignments returns assignments."""

        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_sso_instance_arn="arn:aws:sso:::instance/sso-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "list_account_assignments": {
                        "AccountAssignments": [
                            {
                                "AccountId": "123456789012",
                                "PermissionSetArn": "arn:aws:sso:::permissionSet/ps-1234567890",
                                "PrincipalType": "USER",
                                "PrincipalId": "user-123",
                            }
                        ]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_account_assignments(
            instance_arn="arn:aws:sso:::instance/sso-1234567890",
            account_id="123456789012",
            permission_set_arn="arn:aws:sso:::permissionSet/ps-1234567890",
        )
        assert result.is_success

    def test_list_permission_sets_success(self, monkeypatch, make_fake_client):
        """Test list_permission_sets returns permission sets."""

        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_sso_instance_arn="arn:aws:sso:::instance/sso-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={
                    "list_permission_sets": {
                        "PermissionSets": ["arn:aws:sso:::permissionSet/ps-1234567890"]
                    }
                }
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.list_permission_sets(
            instance_arn="arn:aws:sso:::instance/sso-1234567890"
        )
        assert result.is_success

    def test_healthcheck_with_default_instance_arn(self, monkeypatch, make_fake_client):
        """Test healthcheck uses default_sso_instance_arn."""

        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(
            session_provider=session_provider,
            default_sso_instance_arn="arn:aws:sso:::instance/sso-1234567890",
        )

        def mock_boto3_client(
            service_name, session_config=None, client_config=None, role_arn=None
        ):
            return make_fake_client(
                api_responses={"list_permission_sets": {"PermissionSets": []}}
            )

        monkeypatch.setattr(aws_client, "get_boto3_client", mock_boto3_client)

        result = client.healthcheck()
        assert result.is_success

    def test_healthcheck_missing_default_instance_arn(self):
        """Test healthcheck returns error when default_sso_instance_arn not set."""
        session_provider = SessionProvider(region="us-east-1")
        client = SsoAdminClient(session_provider=session_provider)

        result = client.healthcheck()
        assert not result.is_success
        assert result.error_code == "MISSING_SSO_INSTANCE_ARN"
