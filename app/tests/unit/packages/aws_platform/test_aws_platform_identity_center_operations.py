"""Behavior tests for IdentityCenterAdapter operations.

A real boto3 identitystore client built with static dummy credentials is wrapped
in botocore.stub.Stubber, which validates requests against the service model and
replays canned responses. Each operation test covers the success path with
expected params (including IdentityStoreId) and the data shape, pagination across
two pages with NextToken, conditional Filters, and classification paths for
ResourceNotFoundException, AccessDeniedException, ThrottlingException,
ConflictException, BotoCoreError transient errors, and unmapped errors propagating.
Healthcheck succeeds on an empty Users page.
"""

from typing import Any

import boto3
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from botocore.stub import Stubber

from infrastructure.operations.status import OperationStatus
from packages.aws_platform.adapters.identity_center import IdentityCenterAdapter

pytestmark = pytest.mark.unit


def _identitystore_client() -> Any:
    """Build a real boto3 identitystore client with dummy static credentials."""
    return boto3.client(
        "identitystore",
        region_name="ca-central-1",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


class TestHealthcheck:
    """Healthcheck succeeds when ListUsers returns a page (empty or not)."""

    def test_healthcheck_returns_success_with_true_on_list_users_success(self) -> None:
        """ListUsers with MaxResults=1 succeeds; result.data is True."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_users",
                {"Users": []},
                expected_params={"IdentityStoreId": "d-1234567890", "MaxResults": 1},
            )

            result = adapter.healthcheck()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True

    def test_healthcheck_succeeds_on_non_empty_page(self) -> None:
        """Empty store is healthy; single page with users is also healthy."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_users",
                {"Users": [{"UserId": "user-123"}]},
                expected_params={"IdentityStoreId": "d-1234567890", "MaxResults": 1},
            )

            result = adapter.healthcheck()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True


class TestCreateUser:
    """CreateUser uses the no-retry client and returns UserId."""

    def test_create_user_success_payload_and_data(self) -> None:
        """CreateUser payload includes email, name, and display name; returns UserId."""
        no_retry_client = _identitystore_client()
        std_client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=std_client,
            identitystore_no_retry=no_retry_client,
            identity_store_id="d-1234567890",
        )

        with Stubber(no_retry_client) as stub:
            stub.add_response(
                "create_user",
                {"UserId": "user-456"},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "UserName": "alice@example.com",
                    "Emails": [{"Value": "alice@example.com", "Type": "WORK", "Primary": True}],
                    "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
                    "DisplayName": "Alice Smith",
                },
            )

            result = adapter.create_user("alice@example.com", "Alice", "Smith")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == "user-456"

    def test_create_user_on_no_retry_client_only(self) -> None:
        """CreateUser must be sent through the no-retry client."""
        no_retry_client = _identitystore_client()
        std_client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=std_client,
            identitystore_no_retry=no_retry_client,
            identity_store_id="d-1234567890",
        )

        with Stubber(std_client) as std_stub, Stubber(no_retry_client) as no_retry_stub:
            no_retry_stub.add_response(
                "create_user",
                {"UserId": "user-456"},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "UserName": "bob@example.com",
                    "Emails": [{"Value": "bob@example.com", "Type": "WORK", "Primary": True}],
                    "Name": {"GivenName": "Bob", "FamilyName": "Jones"},
                    "DisplayName": "Bob Jones",
                },
            )

            result = adapter.create_user("bob@example.com", "Bob", "Jones")

            no_retry_stub.assert_no_pending_responses()
            std_stub.assert_no_pending_responses()

        assert result.is_success


class TestDeleteUser:
    """DeleteUser returns True on success."""

    def test_delete_user_success_returns_true(self) -> None:
        """DeleteUser succeeds and returns True."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "delete_user",
                {},
                expected_params={"IdentityStoreId": "d-1234567890", "UserId": "user-123"},
            )

            result = adapter.delete_user("user-123")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True


class TestGetUserId:
    """GetUserId via AlternateIdentifier userName lookup returns UserId."""

    def test_get_user_id_success_by_username(self) -> None:
        """GetUserId with userName AlternateIdentifier returns UserId."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "get_user_id",
                {"UserId": "user-789"},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "AlternateIdentifier": {
                        "UniqueAttribute": {
                            "AttributePath": "userName",
                            "AttributeValue": "alice@example.com",
                        }
                    },
                },
            )

            result = adapter.get_user_id("alice@example.com")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == "user-789"


class TestDescribeUser:
    """DescribeUser returns the user dict without ResponseMetadata and IdentityStoreId."""

    def test_describe_user_success_stripped_dict(self) -> None:
        """DescribeUser returns the response dict minus ResponseMetadata and IdentityStoreId."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "describe_user",
                {
                    "UserId": "user-789",
                    "UserName": "alice@example.com",
                    "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
                    "IdentityStoreId": "d-1234567890",
                    "ResponseMetadata": {"RequestId": "abc123"},
                },
                expected_params={"IdentityStoreId": "d-1234567890", "UserId": "user-789"},
            )

            result = adapter.describe_user("user-789")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == {
            "UserId": "user-789",
            "UserName": "alice@example.com",
            "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
        }


class TestListUsers:
    """ListUsers paginates through Users and only passes Filters when given."""

    def test_list_users_success_single_page(self) -> None:
        """ListUsers flattens single page."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {"UserId": "user-1", "UserName": "alice@example.com"},
                        {"UserId": "user-2", "UserName": "bob@example.com"},
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )

            result = adapter.list_users()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0]["UserId"] == "user-1"
        assert result.data[1]["UserId"] == "user-2"

    def test_list_users_pagination_two_pages(self) -> None:
        """ListUsers flattens users across two pages via NextToken.

        Stub strategy: two canned ListUsers responses on the real client; the
        first carries a NextToken and the second expects that token back, which
        proves the adapter drives the SDK paginator rather than a single call.
        """
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_users",
                {
                    "Users": [{"UserId": "user-1", "UserName": "alice@example.com"}],
                    "NextToken": "token123",
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_users",
                {"Users": [{"UserId": "user-2", "UserName": "bob@example.com"}]},
                expected_params={"IdentityStoreId": "d-1234567890", "NextToken": "token123"},
            )

            result = adapter.list_users()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert [user["UserId"] for user in result.data] == ["user-1", "user-2"]

    def test_list_users_with_filters(self) -> None:
        """ListUsers includes Filters parameter only when filters are provided."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        filters = [{"AttributePath": "name.givenName", "AttributeValue": "Alice"}]

        with Stubber(client) as stub:
            stub.add_response(
                "list_users",
                {"Users": [{"UserId": "user-1", "UserName": "alice@example.com"}]},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "Filters": filters,
                },
            )

            result = adapter.list_users(filters=filters)

            stub.assert_no_pending_responses()

        assert result.is_success


class TestGetGroupId:
    """GetGroupId via AlternateIdentifier displayName lookup returns GroupId."""

    def test_get_group_id_success_by_displayname(self) -> None:
        """GetGroupId with displayName AlternateIdentifier returns GroupId."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "get_group_id",
                {"GroupId": "group-123"},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "AlternateIdentifier": {
                        "UniqueAttribute": {
                            "AttributePath": "displayName",
                            "AttributeValue": "Admins",
                        }
                    },
                },
            )

            result = adapter.get_group_id("Admins")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == "group-123"


class TestListGroups:
    """ListGroups paginates through Groups and only passes Filters when given."""

    def test_list_groups_success_single_page(self) -> None:
        """ListGroups flattens single page."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_groups",
                {
                    "Groups": [
                        {"GroupId": "group-1", "DisplayName": "Admins"},
                        {"GroupId": "group-2", "DisplayName": "Users"},
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )

            result = adapter.list_groups()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0]["GroupId"] == "group-1"

    def test_list_groups_pagination_two_pages(self) -> None:
        """ListGroups flattens groups across two pages via NextToken.

        Stub strategy: two canned ListGroups responses, the second expecting the
        NextToken issued by the first, so a single-call implementation leaves a
        pending response and fails.
        """
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_groups",
                {"Groups": [{"GroupId": "group-1", "DisplayName": "Admins"}], "NextToken": "g-token"},
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_groups",
                {"Groups": [{"GroupId": "group-2", "DisplayName": "Users"}]},
                expected_params={"IdentityStoreId": "d-1234567890", "NextToken": "g-token"},
            )

            result = adapter.list_groups()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert [group["GroupId"] for group in result.data] == ["group-1", "group-2"]

    def test_list_groups_with_filters(self) -> None:
        """ListGroups includes Filters parameter only when filters are provided."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        filters = [{"AttributePath": "displayName", "AttributeValue": "Admins"}]

        with Stubber(client) as stub:
            stub.add_response(
                "list_groups",
                {"Groups": [{"GroupId": "group-1", "DisplayName": "Admins"}]},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "Filters": filters,
                },
            )

            result = adapter.list_groups(filters=filters)

            stub.assert_no_pending_responses()

        assert result.is_success


class TestCreateGroupMembership:
    """CreateGroupMembership uses the no-retry client and returns MembershipId."""

    def test_create_group_membership_success_returns_membership_id(self) -> None:
        """CreateGroupMembership with UserId MemberId returns MembershipId."""
        no_retry_client = _identitystore_client()
        std_client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=std_client,
            identitystore_no_retry=no_retry_client,
            identity_store_id="d-1234567890",
        )

        with Stubber(no_retry_client) as stub:
            stub.add_response(
                "create_group_membership",
                {"MembershipId": "membership-789"},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "group-123",
                    "MemberId": {"UserId": "user-456"},
                },
            )

            result = adapter.create_group_membership("group-123", "user-456")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == "membership-789"


class TestDeleteGroupMembership:
    """DeleteGroupMembership returns True on success."""

    def test_delete_group_membership_success_returns_true(self) -> None:
        """DeleteGroupMembership succeeds and returns True."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "delete_group_membership",
                {},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "MembershipId": "membership-789",
                },
            )

            result = adapter.delete_group_membership("membership-789")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data is True


class TestGetGroupMembershipId:
    """GetGroupMembershipId with UserId MemberId returns MembershipId."""

    def test_get_group_membership_id_success(self) -> None:
        """GetGroupMembershipId returns the MembershipId."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "get_group_membership_id",
                {"MembershipId": "membership-999"},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "group-123",
                    "MemberId": {"UserId": "user-456"},
                },
            )

            result = adapter.get_group_membership_id("group-123", "user-456")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == "membership-999"


class TestListGroupMemberships:
    """ListGroupMemberships paginates through GroupMemberships."""

    def test_list_group_memberships_success_single_page(self) -> None:
        """ListGroupMemberships flattens single page."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [
                        {"MembershipId": "m-1", "MemberId": {"UserId": "user-1"}},
                        {"MembershipId": "m-2", "MemberId": {"UserId": "user-2"}},
                    ]
                },
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "group-123",
                },
            )

            result = adapter.list_group_memberships("group-123")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0]["MembershipId"] == "m-1"

    def test_list_group_memberships_pagination_two_pages(self) -> None:
        """ListGroupMemberships flattens memberships across two pages via NextToken.

        Stub strategy: two canned responses for the same GroupId, the second
        expecting the NextToken from the first; both must be consumed.
        """
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [{"MembershipId": "m-1", "MemberId": {"UserId": "user-1"}}],
                    "NextToken": "m-token",
                },
                expected_params={"IdentityStoreId": "d-1234567890", "GroupId": "group-123"},
            )
            stub.add_response(
                "list_group_memberships",
                {"GroupMemberships": [{"MembershipId": "m-2", "MemberId": {"UserId": "user-2"}}]},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "group-123",
                    "NextToken": "m-token",
                },
            )

            result = adapter.list_group_memberships("group-123")

            stub.assert_no_pending_responses()

        assert result.is_success
        assert [m["MembershipId"] for m in result.data] == ["m-1", "m-2"]


class TestErrorClassification:
    """Errors are classified via classify_aws_error; unmapped errors propagate."""

    def test_resource_not_found_classification(self) -> None:
        """ResourceNotFoundException maps to NOT_FOUND."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "get_user_id",
                service_error_code="ResourceNotFoundException",
                http_status_code=404,
            )

            result = adapter.get_user_id("nonexistent@example.com")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.NOT_FOUND
        assert result.error_code == "ResourceNotFoundException"

    def test_access_denied_classification(self) -> None:
        """AccessDeniedException maps to UNAUTHORIZED."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_users",
                service_error_code="AccessDeniedException",
                http_status_code=403,
            )

            result = adapter.list_users()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == "AccessDeniedException"

    def test_throttling_classification_with_retry_after(self) -> None:
        """ThrottlingException maps to TRANSIENT_ERROR with retry_after=60."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "delete_user",
                service_error_code="ThrottlingException",
                http_status_code=429,
            )

            result = adapter.delete_user("user-123")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"
        assert result.retry_after == 60

    def test_conflict_exception_on_create_user_is_permanent(self) -> None:
        """ConflictException on create_user maps to PERMANENT_ERROR."""
        no_retry_client = _identitystore_client()
        std_client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=std_client,
            identitystore_no_retry=no_retry_client,
            identity_store_id="d-1234567890",
        )

        with Stubber(no_retry_client) as stub:
            stub.add_client_error(
                "create_user",
                service_error_code="ConflictException",
                http_status_code=409,
            )

            result = adapter.create_user("alice@example.com", "Alice", "Smith")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "ConflictException"

    def test_conflict_exception_on_create_group_membership_is_permanent(self) -> None:
        """ConflictException on create_group_membership maps to PERMANENT_ERROR."""
        no_retry_client = _identitystore_client()
        std_client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=std_client,
            identitystore_no_retry=no_retry_client,
            identity_store_id="d-1234567890",
        )

        with Stubber(no_retry_client) as stub:
            stub.add_client_error(
                "create_group_membership",
                service_error_code="ConflictException",
                http_status_code=409,
            )

            result = adapter.create_group_membership("group-123", "user-456")

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.PERMANENT_ERROR
        assert result.error_code == "ConflictException"

    def test_botocore_connection_error_is_transient(self) -> None:
        """BotoCoreError (EndpointConnectionError) maps to TRANSIENT_ERROR."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            # Monkeypatch the client method to raise an endpoint error
            def raise_endpoint_error(*args: Any, **kwargs: Any) -> None:
                raise EndpointConnectionError(endpoint_url="https://identitystore.ca-central-1.amazonaws.com")

            stub.client.list_groups = raise_endpoint_error

            result = adapter.list_groups()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "EndpointConnectionError"

    def test_unmapped_client_error_propagates(self) -> None:
        """ValidationException (unmapped) propagates as ClientError."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "delete_user",
                service_error_code="ValidationException",
                http_status_code=400,
            )

            with pytest.raises(ClientError) as excinfo:
                adapter.delete_user("invalid")

            stub.assert_no_pending_responses()

        assert excinfo.value.response["Error"]["Code"] == "ValidationException"

    def test_programmer_error_propagates(self) -> None:
        """Non-ClientError exceptions (e.g., KeyError) propagate unchanged."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:

            def raise_key_error(*args: Any, **kwargs: Any) -> None:
                raise KeyError("missing_key")

            stub.client.describe_user = raise_key_error

            with pytest.raises(KeyError):
                adapter.describe_user("user-123")

            stub.assert_no_pending_responses()
