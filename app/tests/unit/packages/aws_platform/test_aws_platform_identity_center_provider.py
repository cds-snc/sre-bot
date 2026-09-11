"""Behavior tests for build_identity_center_adapter and client routing.

The provider is monkeypatched to record get_aws_client calls and verify routing:
two calls to get_aws_client('identitystore', ...), the second with retries=False.
Environment variables AWS_SSO_INSTANCE_ID and AWS_ORG_ACCOUNT_ROLE_ARN are set
and get_aws_settings cache is cleared before and after. The adapter receives
two Stubbers: create_user and create_group_membership use the no-retry client,
get_user_id uses the standard-retry client. Both clients assert no pending
responses.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber

from integrations.aws.settings import get_aws_settings
from packages.aws_platform.adapters.identity_center import build_identity_center_adapter

pytestmark = pytest.mark.unit


def _identitystore_client() -> Any:
    """Build a real boto3 identitystore client with dummy static credentials."""
    return boto3.client(
        "identitystore",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestBuildIdentityCenterAdapter:
    """build_identity_center_adapter routes clients and reads settings."""

    @pytest.fixture(autouse=True)
    def clear_settings_cache(self) -> Iterator[None]:
        """Clear settings cache before and after each test."""
        get_aws_settings.cache_clear()
        yield
        get_aws_settings.cache_clear()

    def test_two_get_aws_client_calls_standard_and_no_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """build_identity_center_adapter calls get_aws_client twice: standard and no-retry."""
        monkeypatch.setenv("AWS_SSO_INSTANCE_ID", "d-1234567890")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")

        get_aws_client_calls: list[dict[str, Any]] = []

        def record_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            get_aws_client_calls.append(
                {
                    "service_name": service_name,
                    "role_arn": role_arn,
                    "session_name": session_name,
                    "retries": retries,
                }
            )
            return _identitystore_client()

        with patch(
            "packages.aws_platform.adapters.identity_center.get_aws_client",
            side_effect=record_get_aws_client,
        ):
            _ = build_identity_center_adapter()

        assert len(get_aws_client_calls) == 2
        # First call: standard retry
        assert get_aws_client_calls[0]["service_name"] == "identitystore"
        assert get_aws_client_calls[0]["role_arn"] == "arn:aws:iam::123456789012:role/org-role"
        assert get_aws_client_calls[0]["retries"] is True

        # Second call: no retry
        assert get_aws_client_calls[1]["service_name"] == "identitystore"
        assert get_aws_client_calls[1]["role_arn"] == "arn:aws:iam::123456789012:role/org-role"
        assert get_aws_client_calls[1]["retries"] is False

    def test_role_arn_from_service_role_map(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Role ARN is read from SERVICE_ROLE_MAP['identitystore']."""
        monkeypatch.setenv("AWS_SSO_INSTANCE_ID", "d-1234567890")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")

        get_aws_client_calls: list[dict[str, Any]] = []

        def record_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            get_aws_client_calls.append({"role_arn": role_arn})
            return _identitystore_client()

        with patch(
            "packages.aws_platform.adapters.identity_center.get_aws_client",
            side_effect=record_get_aws_client,
        ):
            _ = build_identity_center_adapter()

        # Both calls should have the role ARN from SERVICE_ROLE_MAP
        assert get_aws_client_calls[0]["role_arn"] == "arn:aws:iam::123456789012:role/org-role"
        assert get_aws_client_calls[1]["role_arn"] == "arn:aws:iam::123456789012:role/org-role"

    def test_role_arn_none_when_setting_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Role ARN is None when AWS_ORG_ACCOUNT_ROLE_ARN is empty."""
        monkeypatch.setenv("AWS_SSO_INSTANCE_ID", "d-1234567890")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "")

        get_aws_client_calls: list[dict[str, Any]] = []

        def record_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            get_aws_client_calls.append({"role_arn": role_arn})
            return _identitystore_client()

        with patch(
            "packages.aws_platform.adapters.identity_center.get_aws_client",
            side_effect=record_get_aws_client,
        ):
            _ = build_identity_center_adapter()

        # Both calls should have None role ARN
        assert get_aws_client_calls[0]["role_arn"] is None
        assert get_aws_client_calls[1]["role_arn"] is None

    def test_identity_store_id_from_aws_sso_instance_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """IdentityStoreId sent on the wire comes from AWS_SSO_INSTANCE_ID.

        Stub strategy: the built adapter issues one GetUserId whose expected
        params pin the IdentityStoreId, so the assertion is on the request the
        SDK would send rather than on adapter internals.
        """
        monkeypatch.setenv("AWS_SSO_INSTANCE_ID", "d-9876543210")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")

        client = _identitystore_client()

        def stub_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            return client

        with patch(
            "packages.aws_platform.adapters.identity_center.get_aws_client",
            side_effect=stub_get_aws_client,
        ):
            adapter = build_identity_center_adapter()

        with Stubber(client) as stub:
            stub.add_response(
                "get_user_id",
                {"UserId": "user-1", "IdentityStoreId": "d-9876543210"},
                expected_params={
                    "IdentityStoreId": "d-9876543210",
                    "AlternateIdentifier": {
                        "UniqueAttribute": {"AttributePath": "userName", "AttributeValue": "alice@example.com"}
                    },
                },
            )

            result = adapter.get_user_id("alice@example.com")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == "user-1"

    def test_create_user_uses_no_retry_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CreateUser is sent through the no-retry client."""
        monkeypatch.setenv("AWS_SSO_INSTANCE_ID", "d-1234567890")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")

        std_client = _identitystore_client()
        no_retry_client = _identitystore_client()

        def stub_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            return std_client if retries else no_retry_client

        with patch(
            "packages.aws_platform.adapters.identity_center.get_aws_client",
            side_effect=stub_get_aws_client,
        ):
            adapter = build_identity_center_adapter()

            with Stubber(std_client) as std_stub, Stubber(no_retry_client) as no_retry_stub:
                # Only register on no_retry_stub
                no_retry_stub.add_response(
                    "create_user",
                    {"UserId": "user-123"},
                    expected_params={
                        "IdentityStoreId": "d-1234567890",
                        "UserName": "test@example.com",
                        "Emails": [{"Value": "test@example.com", "Type": "WORK", "Primary": True}],
                        "Name": {"GivenName": "Test", "FamilyName": "User"},
                        "DisplayName": "Test User",
                    },
                )

                result = adapter.create_user("test@example.com", "Test", "User")

                no_retry_stub.assert_no_pending_responses()
                std_stub.assert_no_pending_responses()

        assert result.is_success

    def test_get_user_id_uses_standard_retry_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """GetUserId is sent through the standard-retry client."""
        monkeypatch.setenv("AWS_SSO_INSTANCE_ID", "d-1234567890")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")

        std_client = _identitystore_client()
        no_retry_client = _identitystore_client()

        def stub_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            return std_client if retries else no_retry_client

        with patch(
            "packages.aws_platform.adapters.identity_center.get_aws_client",
            side_effect=stub_get_aws_client,
        ):
            adapter = build_identity_center_adapter()

            with Stubber(std_client) as std_stub, Stubber(no_retry_client) as no_retry_stub:
                # Only register on std_stub
                std_stub.add_response(
                    "get_user_id",
                    {"UserId": "user-789"},
                    expected_params={
                        "IdentityStoreId": "d-1234567890",
                        "AlternateIdentifier": {
                            "UniqueAttribute": {
                                "AttributePath": "userName",
                                "AttributeValue": "test@example.com",
                            }
                        },
                    },
                )

                result = adapter.get_user_id("test@example.com")

                std_stub.assert_no_pending_responses()
                no_retry_stub.assert_no_pending_responses()

        assert result.is_success

    def test_create_group_membership_uses_no_retry_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CreateGroupMembership is sent through the no-retry client."""
        monkeypatch.setenv("AWS_SSO_INSTANCE_ID", "d-1234567890")
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")

        std_client = _identitystore_client()
        no_retry_client = _identitystore_client()

        def stub_get_aws_client(
            service_name: str,
            *,
            role_arn: str | None = None,
            session_name: str = "sre-bot",
            retries: bool = True,
        ) -> Any:
            return std_client if retries else no_retry_client

        with patch(
            "packages.aws_platform.adapters.identity_center.get_aws_client",
            side_effect=stub_get_aws_client,
        ):
            adapter = build_identity_center_adapter()

            with Stubber(std_client) as std_stub, Stubber(no_retry_client) as no_retry_stub:
                # Only register on no_retry_stub
                no_retry_stub.add_response(
                    "create_group_membership",
                    {"MembershipId": "membership-123"},
                    expected_params={
                        "IdentityStoreId": "d-1234567890",
                        "GroupId": "group-456",
                        "MemberId": {"UserId": "user-789"},
                    },
                )

                result = adapter.create_group_membership("group-456", "user-789")

                no_retry_stub.assert_no_pending_responses()
                std_stub.assert_no_pending_responses()

        assert result.is_success
