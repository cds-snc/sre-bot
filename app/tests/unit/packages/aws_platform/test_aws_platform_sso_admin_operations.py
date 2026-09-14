"""Behavior tests for SsoAdminAdapter operations.

A real boto3 sso-admin client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params and the data shape, pagination where applicable via NextToken,
predefined permission set resolution, and classification paths for AWS errors.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.sso_admin import SsoAdminAdapter

pytestmark = pytest.mark.unit


def _sso_admin_client() -> Any:
    """Build a real boto3 sso-admin client with dummy static credentials."""
    return boto3.client(
        "sso-admin",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestCreateAccountAssignment:
    """CreateAccountAssignment assigns permissions to a user."""

    def test_create_account_assignment_success_status_not_failed(self) -> None:
        """CreateAccountAssignment succeeds when status is not FAILED."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "create_account_assignment",
                {
                    "AccountAssignmentCreationStatus": {
                        "Status": "IN_PROGRESS",
                        "RequestId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "CreatedDate": 1234567890.0,
                    }
                },
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "TargetId": "123456789012",
                    "TargetType": "AWS_ACCOUNT",
                    "PermissionSetArn": "arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
                    "PrincipalType": "USER",
                    "PrincipalId": "user-123",
                },
            )

            result = adapter.create_account_assignment(
                user_id="user-123",
                account_id="123456789012",
                permission_set="write",
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True

    def test_create_account_assignment_failed_status_returns_false(self) -> None:
        """CreateAccountAssignment returns False when status is FAILED."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "create_account_assignment",
                {
                    "AccountAssignmentCreationStatus": {
                        "Status": "FAILED",
                        "RequestId": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                        "CreatedDate": 1234567890.0,
                    }
                },
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "TargetId": "123456789012",
                    "TargetType": "AWS_ACCOUNT",
                    "PermissionSetArn": "arn:aws:sso::aws:permissionSet/view-only",
                    "PrincipalType": "USER",
                    "PrincipalId": "user-456",
                },
            )

            result = adapter.create_account_assignment(
                user_id="user-456",
                account_id="123456789012",
                permission_set="read",
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is False

    def test_create_account_assignment_resolves_predefined_permission_sets(self) -> None:
        """'write' and 'read' resolve to the configured ARNs; any other value is sent verbatim.

        Three responses are queued in call order and each pins PermissionSetArn in
        its expected params, so a wrong mapping fails Stubber request validation.
        """
        client = _sso_admin_client()
        system_admin_arn = "arn:aws:sso::aws:permissionSet/custom-admin"
        view_only_arn = "arn:aws:sso::aws:permissionSet/custom-viewer"
        explicit_arn = "arn:aws:sso::aws:permissionSet/explicit-set"
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions=system_admin_arn,
            view_only_permissions=view_only_arn,
        )
        cases = [("write", system_admin_arn), ("read", view_only_arn), (explicit_arn, explicit_arn)]

        with Stubber(client) as stub:
            for _, expected_arn in cases:
                stub.add_response(
                    "create_account_assignment",
                    {
                        "AccountAssignmentCreationStatus": {
                            "Status": "IN_PROGRESS",
                            "RequestId": "cccccccc-cccc-cccc-cccc-cccccccccccc",
                            "CreatedDate": 1234567890.0,
                        }
                    },
                    expected_params={
                        "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                        "TargetId": "999999999999",
                        "TargetType": "AWS_ACCOUNT",
                        "PermissionSetArn": expected_arn,
                        "PrincipalType": "USER",
                        "PrincipalId": "user-789",
                    },
                )

            results = [
                adapter.create_account_assignment(
                    user_id="user-789",
                    account_id="999999999999",
                    permission_set=name,
                )
                for name, _ in cases
            ]

            stub.assert_no_pending_responses()

        assert [(r.is_success, r.data) for r in results] == [(True, True)] * 3


class TestDeleteAccountAssignment:
    """DeleteAccountAssignment removes permissions from a user."""

    def test_delete_account_assignment_success_status_not_failed(self) -> None:
        """DeleteAccountAssignment succeeds when status is not FAILED."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "delete_account_assignment",
                {
                    "AccountAssignmentDeletionStatus": {
                        "Status": "IN_PROGRESS",
                        "RequestId": "dddddddd-dddd-dddd-dddd-dddddddddddd",
                        "CreatedDate": 1234567890.0,
                    }
                },
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "TargetId": "123456789012",
                    "TargetType": "AWS_ACCOUNT",
                    "PermissionSetArn": "arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
                    "PrincipalType": "USER",
                    "PrincipalId": "user-123",
                },
            )

            result = adapter.delete_account_assignment(
                user_id="user-123",
                account_id="123456789012",
                permission_set="write",
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True

    def test_delete_account_assignment_failed_status_returns_false(self) -> None:
        """DeleteAccountAssignment returns False when status is FAILED."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "delete_account_assignment",
                {
                    "AccountAssignmentDeletionStatus": {
                        "Status": "FAILED",
                        "RequestId": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                        "CreatedDate": 1234567890.0,
                    }
                },
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "TargetId": "123456789012",
                    "TargetType": "AWS_ACCOUNT",
                    "PermissionSetArn": "arn:aws:sso::aws:permissionSet/view-only",
                    "PrincipalType": "USER",
                    "PrincipalId": "user-456",
                },
            )

            result = adapter.delete_account_assignment(
                user_id="user-456",
                account_id="123456789012",
                permission_set="read",
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is False


class TestListAccountAssignmentsForPrincipal:
    """ListAccountAssignmentsForPrincipal returns account assignments for a user."""

    def test_list_account_assignments_success_single_page(self) -> None:
        """ListAccountAssignmentsForPrincipal with single page returns list of assignments."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_account_assignments_for_principal",
                {
                    "AccountAssignments": [
                        {
                            "AccountId": "123456789012",
                            "PermissionSetArn": "arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
                            "PrincipalType": "USER",
                            "PrincipalId": "user-123",
                        }
                    ]
                },
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "PrincipalId": "user-123",
                    "PrincipalType": "USER",
                },
            )

            result = adapter.list_account_assignments_for_principal(
                principal_id="user-123",
                principal_type="USER",
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["AccountId"] == "123456789012"

    def test_list_account_assignments_pagination_two_pages(self) -> None:
        """ListAccountAssignmentsForPrincipal flattens assignments across two pages via NextToken."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_account_assignments_for_principal",
                {
                    "AccountAssignments": [
                        {
                            "AccountId": "111111111111",
                            "PermissionSetArn": "arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
                            "PrincipalType": "USER",
                            "PrincipalId": "user-123",
                        }
                    ],
                    "NextToken": "assignments-token",
                },
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "PrincipalId": "user-123",
                    "PrincipalType": "USER",
                },
            )
            stub.add_response(
                "list_account_assignments_for_principal",
                {
                    "AccountAssignments": [
                        {
                            "AccountId": "222222222222",
                            "PermissionSetArn": "arn:aws:sso::aws:permissionSet/view-only",
                            "PrincipalType": "USER",
                            "PrincipalId": "user-123",
                        }
                    ]
                },
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "PrincipalId": "user-123",
                    "PrincipalType": "USER",
                    "NextToken": "assignments-token",
                },
            )

            result = adapter.list_account_assignments_for_principal(
                principal_id="user-123",
                principal_type="USER",
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert [a["AccountId"] for a in result.data] == ["111111111111", "222222222222"]

    def test_list_account_assignments_empty(self) -> None:
        """ListAccountAssignmentsForPrincipal with no assignments returns empty list."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_account_assignments_for_principal",
                {"AccountAssignments": []},
                expected_params={
                    "InstanceArn": "arn:aws:sso::123456789012:instance/sso-instance-id",
                    "PrincipalId": "user-456",
                    "PrincipalType": "USER",
                },
            )

            result = adapter.list_account_assignments_for_principal(
                principal_id="user-456",
                principal_type="USER",
            )

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_resource_not_found_classification(self) -> None:
        """ResourceNotFoundException maps to NOT_FOUND."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_account_assignments_for_principal",
                service_error_code="ResourceNotFoundException",
                http_status_code=404,
            )

            result = adapter.list_account_assignments_for_principal(
                principal_id="nonexistent",
                principal_type="USER",
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "ResourceNotFoundException"

    def test_access_denied_classification(self) -> None:
        """AccessDeniedException maps to UNAUTHORIZED."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_account_assignments_for_principal",
                service_error_code="AccessDeniedException",
                http_status_code=403,
            )

            result = adapter.list_account_assignments_for_principal(
                principal_id="user-123",
                principal_type="USER",
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == "AccessDeniedException"

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "create_account_assignment",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.create_account_assignment(
                user_id="user-123",
                account_id="123456789012",
                permission_set="write",
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:

            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://sso.ca-central-1.amazonaws.com")

            stub.client.list_account_assignments_for_principal = raise_endpoint_error

            result = adapter.list_account_assignments_for_principal(
                principal_id="user-123",
                principal_type="USER",
            )

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "create_account_assignment",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.create_account_assignment(
                    user_id="invalid",
                    account_id="123456789012",
                    permission_set="write",
                )

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _sso_admin_client()
        adapter = SsoAdminAdapter(
            client=client,
            instance_arn="arn:aws:sso::123456789012:instance/sso-instance-id",
            system_admin_permissions="arn:aws:sso::aws:permissionSet/aws-sso-system-admin",
            view_only_permissions="arn:aws:sso::aws:permissionSet/view-only",
        )

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.list_account_assignments_for_principal = raise_key_error

            with pytest.raises(KeyError):
                adapter.list_account_assignments_for_principal(
                    principal_id="user-123",
                    principal_type="USER",
                )

            stub.assert_no_pending_responses()
