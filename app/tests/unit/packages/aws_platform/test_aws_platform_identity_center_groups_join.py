"""Behavior tests for IdentityCenterAdapter.list_groups_with_memberships.

The join operation applies group filters, projects group dicts to four keys,
lists all users once, then per group lists memberships and merges user details.
Failed list_groups or list_users return their failure result with no further
calls. Per-group membership failures are logged and the group skipped. Missing
users drop the group when tolerate_errors=False and keep it when True. Empty
groups list returns success([]) with no list_users call. Groups with no
memberships are omitted from the result.
"""

from typing import Any

import boto3
import pytest
from botocore.stub import Stubber

from contracts.operations.status import OperationStatus
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


class TestListGroupsWithMemberships:
    """list_groups_with_memberships handles filtering, joining, and error paths."""

    def test_empty_groups_returns_empty_list_no_list_users_call(self) -> None:
        """Empty groups list returns success([]) without calling list_users."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_response(
                "list_groups",
                {"Groups": []},
                expected_params={"IdentityStoreId": "d-1234567890"},
            )

            result = adapter.list_groups_with_memberships()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []

    def test_group_filters_applied_via_callables(self) -> None:
        """Group filters are applied; only matching groups proceed to membership lookup."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        def filter_admins(group: dict[str, Any]) -> bool:
            return "admin" in group.get("DisplayName", "").lower()

        with Stubber(client) as stub:
            stub.add_response(
                "list_groups",
                {
                    "Groups": [
                        {
                            "GroupId": "g-1",
                            "DisplayName": "Admins",
                            "Description": "Admin users",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        },
                        {
                            "GroupId": "g-2",
                            "DisplayName": "Users",
                            "Description": "Regular users",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-ac6b48cb-49bf-522d-a39b-1212de06e9c5",
                            "Revision": "1",
                        },
                        {
                            "GroupId": "g-3",
                            "DisplayName": "Superadmins",
                            "Description": "Super users",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-b3003da5-f84f-5fc6-bdba-dbf1ccf7b3c5",
                            "Revision": "1",
                        },
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            # Only g-1 and g-3 pass the filter
            stub.add_response(
                "list_users",
                {"Users": []},
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            # Only memberships for filtered groups are requested
            stub.add_response(
                "list_group_memberships",
                {"GroupMemberships": []},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-1",
                },
            )
            stub.add_response(
                "list_group_memberships",
                {"GroupMemberships": []},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-3",
                },
            )

            result = adapter.list_groups_with_memberships(groups_filters=[filter_admins])

            stub.assert_no_pending_responses()

        assert result.is_success
        assert result.data == []  # All groups have no memberships

    def test_groups_projected_to_four_keys(self) -> None:
        """Groups are projected to GroupId, DisplayName, Description, IdentityStoreId."""
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
                        {
                            "GroupId": "g-1",
                            "IdentityStoreId": "d-1234567890",
                            "DisplayName": "Admins",
                            "Description": "Admin users",
                            "CreatedBy": "should be removed",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {
                            "UserId": "user-1",
                            "UserName": "alice@example.com",
                            "IdentityStoreId": "d-1234567890",
                            "UserArn": "arn:aws:identitystore:::user/1234567890-e9f7230f-ccb4-582f-82d6-c636512ef431",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [
                        {
                            "MembershipId": "m-1",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-1"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-3387dab8-bada-55e6-9092-0064c468c58c",
                        }
                    ]
                },
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-1",
                },
            )

            result = adapter.list_groups_with_memberships()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        group = result.data[0]
        assert "GroupId" in group
        assert "DisplayName" in group
        assert "Description" in group
        assert "IdentityStoreId" in group
        assert group["GroupId"] == "g-1"
        assert "CreatedBy" not in group

    def test_user_details_merged_into_membership(self) -> None:
        """User details (UserId, UserName, Name, Emails) are merged into membership['MemberId']."""
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
                        {
                            "GroupId": "g-1",
                            "DisplayName": "Admins",
                            "Description": "Admin users",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {
                            "UserId": "user-1",
                            "UserName": "alice@example.com",
                            "IdentityStoreId": "d-1234567890",
                            "Name": {"GivenName": "Alice", "FamilyName": "Smith"},
                            "Emails": [{"Value": "alice@example.com", "Type": "WORK"}],
                            "UserArn": "arn:aws:identitystore:::user/1234567890-e9f7230f-ccb4-582f-82d6-c636512ef431",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [
                        {
                            "MembershipId": "m-1",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-1"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-3387dab8-bada-55e6-9092-0064c468c58c",
                        }
                    ]
                },
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-1",
                },
            )

            result = adapter.list_groups_with_memberships()

            stub.assert_no_pending_responses()

        assert result.is_success
        assert len(result.data) == 1
        group = result.data[0]
        assert len(group["GroupMemberships"]) == 1
        membership = group["GroupMemberships"][0]
        assert membership["MembershipId"] == "m-1"
        assert membership["MemberId"]["UserId"] == "user-1"
        assert membership["MemberId"]["UserName"] == "alice@example.com"
        assert membership["MemberId"]["Name"]["GivenName"] == "Alice"

    def test_group_membership_failure_skipped_and_logged(self) -> None:
        """A failed list_group_memberships is logged and the group skipped; others proceed."""
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
                        {
                            "GroupId": "g-1",
                            "DisplayName": "Admins",
                            "Description": "Group",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        },
                        {
                            "GroupId": "g-2",
                            "DisplayName": "Users",
                            "Description": "Group",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-ac6b48cb-49bf-522d-a39b-1212de06e9c5",
                            "Revision": "1",
                        },
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {
                            "UserId": "user-2",
                            "UserName": "bob@example.com",
                            "IdentityStoreId": "d-1234567890",
                            "UserArn": "arn:aws:identitystore:::user/1234567890-4b15e443-cf48-5b71-8fd6-4e52809ffbd5",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            # g-1 fails
            stub.add_client_error(
                "list_group_memberships",
                service_error_code="AccessDeniedException",
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-1",
                },
            )
            # g-2 succeeds with one membership
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [
                        {
                            "MembershipId": "m-2",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-2"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-1cce2af6-1337-5995-824f-3f978b6d4cd6",
                        }
                    ]
                },
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-2",
                },
            )

            result = adapter.list_groups_with_memberships()

            stub.assert_no_pending_responses()

        assert result.is_success
        # Only g-2 survives: g-1's membership listing failed and was skipped, the run still succeeds.
        assert [group["GroupId"] for group in result.data] == ["g-2"]
        assert result.data[0]["GroupMemberships"][0]["MemberId"]["UserName"] == "bob@example.com"

    def test_missing_user_drops_group_when_tolerate_errors_false(self) -> None:
        """A membership whose user is absent drops the group when tolerate_errors=False."""
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
                        {
                            "GroupId": "g-1",
                            "DisplayName": "Admins",
                            "Description": "Group",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {
                            "UserId": "user-1",
                            "UserName": "alice@example.com",
                            "IdentityStoreId": "d-1234567890",
                            "Name": {"GivenName": "Alice"},
                            "UserArn": "arn:aws:identitystore:::user/1234567890-e9f7230f-ccb4-582f-82d6-c636512ef431",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [
                        {
                            "MembershipId": "m-1",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-1"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-3387dab8-bada-55e6-9092-0064c468c58c",
                        },
                        {
                            "MembershipId": "m-2",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-2"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-1cce2af6-1337-5995-824f-3f978b6d4cd6",
                        },  # user-2 missing
                    ]
                },
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-1",
                },
            )

            result = adapter.list_groups_with_memberships(tolerate_errors=False)

            stub.assert_no_pending_responses()

        # Group is dropped because user-2 is missing
        assert result.is_success
        assert result.data == []

    def test_missing_user_keeps_group_when_tolerate_errors_true(self) -> None:
        """A membership whose user is absent keeps the group when tolerate_errors=True."""
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
                        {
                            "GroupId": "g-1",
                            "DisplayName": "Admins",
                            "Description": "Group",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {
                            "UserId": "user-1",
                            "UserName": "alice@example.com",
                            "IdentityStoreId": "d-1234567890",
                            "Name": {"GivenName": "Alice"},
                            "UserArn": "arn:aws:identitystore:::user/1234567890-e9f7230f-ccb4-582f-82d6-c636512ef431",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [
                        {
                            "MembershipId": "m-1",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-1"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-3387dab8-bada-55e6-9092-0064c468c58c",
                        },
                        {
                            "MembershipId": "m-2",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-2"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-1cce2af6-1337-5995-824f-3f978b6d4cd6",
                        },
                    ]
                },
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-1",
                },
            )

            result = adapter.list_groups_with_memberships(tolerate_errors=True)

            stub.assert_no_pending_responses()

        # Group is kept with the available user
        assert result.is_success
        assert len(result.data) == 1

    def test_failed_list_groups_returns_failure_no_further_calls(self) -> None:
        """A failed list_groups returns that failure result with no further calls."""
        client = _identitystore_client()
        adapter = IdentityCenterAdapter(
            identitystore=client,
            identitystore_no_retry=client,
            identity_store_id="d-1234567890",
        )

        with Stubber(client) as stub:
            stub.add_client_error(
                "list_groups",
                service_error_code="AccessDeniedException",
                expected_params={"IdentityStoreId": "d-1234567890"},
            )

            result = adapter.list_groups_with_memberships()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.UNAUTHORIZED
        assert result.error_code == "AccessDeniedException"

    def test_failed_list_users_returns_failure_no_further_calls(self) -> None:
        """A failed list_users returns that failure result with no further calls."""
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
                        {
                            "GroupId": "g-1",
                            "DisplayName": "Admins",
                            "Description": "Group",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_client_error(
                "list_users",
                service_error_code="ThrottlingException",
                expected_params={"IdentityStoreId": "d-1234567890"},
            )

            result = adapter.list_groups_with_memberships()

            stub.assert_no_pending_responses()

        assert result.status == OperationStatus.TRANSIENT_ERROR
        assert result.error_code == "ThrottlingException"

    def test_groups_with_no_memberships_omitted(self) -> None:
        """Groups with no memberships are omitted from the result."""
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
                        {
                            "GroupId": "g-1",
                            "DisplayName": "Admins",
                            "Description": "Group",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-1bdd323c-938f-5d7b-8dfa-7f6d666522ac",
                            "Revision": "1",
                        },
                        {
                            "GroupId": "g-2",
                            "DisplayName": "Users",
                            "Description": "Group",
                            "IdentityStoreId": "d-1234567890",
                            "GroupArn": "arn:aws:identitystore:::group/1234567890-ac6b48cb-49bf-522d-a39b-1212de06e9c5",
                            "Revision": "1",
                        },
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {
                            "UserId": "user-1",
                            "UserName": "alice@example.com",
                            "IdentityStoreId": "d-1234567890",
                            "UserArn": "arn:aws:identitystore:::user/1234567890-e9f7230f-ccb4-582f-82d6-c636512ef431",
                            "Revision": "1",
                        }
                    ]
                },
                expected_params={"IdentityStoreId": "d-1234567890"},
            )
            # g-1 has no memberships
            stub.add_response(
                "list_group_memberships",
                {"GroupMemberships": []},
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-1",
                },
            )
            # g-2 has a membership
            stub.add_response(
                "list_group_memberships",
                {
                    "GroupMemberships": [
                        {
                            "MembershipId": "m-1",
                            "IdentityStoreId": "d-1234567890",
                            "MemberId": {"UserId": "user-1"},
                            "MembershipArn": "arn:aws:identitystore:::membership/1234567890-3387dab8-bada-55e6-9092-0064c468c58c",
                        }
                    ]
                },
                expected_params={
                    "IdentityStoreId": "d-1234567890",
                    "GroupId": "g-2",
                },
            )

            result = adapter.list_groups_with_memberships()

            stub.assert_no_pending_responses()

        # Only g-2 is in the result (g-1 has no memberships)
        assert result.is_success
        assert len(result.data) == 1
        assert result.data[0]["GroupId"] == "g-2"
