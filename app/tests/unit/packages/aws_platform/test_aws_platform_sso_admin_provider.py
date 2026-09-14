"""Behavior tests for build_sso_admin_adapter client construction and settings wiring.

get_aws_client is patched in the adapter module to record its arguments and
return a real boto3 sso-admin client with dummy static credentials. Settings come
from environment variables with the settings cache cleared around each test.
Role routing is asserted on the recorded call; instance ARN and permission set
wiring are asserted on the wire through Stubber expected params, so the check is
on the request the SDK would send rather than on adapter internals.
"""

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from botocore.stub import Stubber

from integrations.aws.settings import get_aws_settings
from packages.aws_platform.adapters.sso_admin import SsoAdminAdapter, build_sso_admin_adapter

pytestmark = pytest.mark.unit

_INSTANCE_ARN = "arn:aws:sso:::instance/ssoins-1234567890abcdef"
_ADMIN_ARN = "arn:aws:sso:::permissionSet/ssoins-1234567890abcdef/ps-admin"
_VIEW_ONLY_ARN = "arn:aws:sso:::permissionSet/ssoins-1234567890abcdef/ps-viewer"


def _sso_admin_client() -> Any:
    """Build a real boto3 sso-admin client with dummy static credentials."""
    return boto3.client(
        "sso-admin",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestBuildSsoAdminAdapter:
    """build_sso_admin_adapter builds one sso-admin client and wires SSO settings."""

    @pytest.fixture(autouse=True)
    def sso_settings(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
        """Set SSO settings and clear the settings cache before and after each test."""
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "arn:aws:iam::123456789012:role/org-role")
        monkeypatch.setenv("AWS_SSO_INSTANCE_ARN", _INSTANCE_ARN)
        monkeypatch.setenv("AWS_SSO_SYSTEM_ADMIN_PERMISSIONS", _ADMIN_ARN)
        monkeypatch.setenv("AWS_SSO_VIEW_ONLY_PERMISSIONS", _VIEW_ONLY_ARN)
        get_aws_settings.cache_clear()
        yield
        get_aws_settings.cache_clear()

    def _build(self, client: Any, calls: list[dict[str, Any]]) -> SsoAdminAdapter:
        def record_get_aws_client(service_name: str, *, role_arn: str | None = None, **kwargs: Any) -> Any:
            calls.append({"service_name": service_name, "role_arn": role_arn, **kwargs})
            return client

        with patch(
            "packages.aws_platform.adapters.sso_admin.get_aws_client",
            side_effect=record_get_aws_client,
            create=True,
        ):
            return build_sso_admin_adapter()

    def test_single_sso_admin_client_with_org_role(self) -> None:
        """One get_aws_client('sso-admin') call carries SERVICE_ROLE_MAP['sso-admin']."""
        calls: list[dict[str, Any]] = []

        adapter = self._build(_sso_admin_client(), calls)

        assert isinstance(adapter, SsoAdminAdapter)
        assert len(calls) == 1
        assert calls[0]["service_name"] == "sso-admin"
        assert calls[0]["role_arn"] == "arn:aws:iam::123456789012:role/org-role"

    def test_role_arn_none_when_setting_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty AWS_ORG_ACCOUNT_ROLE_ARN is passed as role_arn=None, not an empty string."""
        monkeypatch.setenv("AWS_ORG_ACCOUNT_ROLE_ARN", "")
        get_aws_settings.cache_clear()
        calls: list[dict[str, Any]] = []

        self._build(_sso_admin_client(), calls)

        assert calls[0]["role_arn"] is None

    def test_instance_arn_and_permission_sets_come_from_settings(self) -> None:
        """InstanceArn and the 'write'/'read' PermissionSetArn sent on the wire come from settings."""
        client = _sso_admin_client()
        adapter = self._build(client, [])

        with Stubber(client) as stub:
            for expected_arn in (_ADMIN_ARN, _VIEW_ONLY_ARN):
                stub.add_response(
                    "create_account_assignment",
                    {"AccountAssignmentCreationStatus": {"Status": "IN_PROGRESS"}},
                    expected_params={
                        "InstanceArn": _INSTANCE_ARN,
                        "TargetId": "123456789012",
                        "TargetType": "AWS_ACCOUNT",
                        "PermissionSetArn": expected_arn,
                        "PrincipalType": "USER",
                        "PrincipalId": "user-123",
                    },
                )

            write_result = adapter.create_account_assignment("user-123", "123456789012", "write")
            read_result = adapter.create_account_assignment("user-123", "123456789012", "read")

            stub.assert_no_pending_responses()

        assert write_result.is_success
        assert read_result.is_success
