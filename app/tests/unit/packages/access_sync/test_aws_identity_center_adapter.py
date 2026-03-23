"""Unit tests for the AWS Identity Center access-sync adapter."""

from typing import Any, cast

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.access_sync.adapters.aws_identity_center import AwsIdentityCenterAdapter


class FakeIdentityStoreClient:
    """Minimal Identity Store client test double."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.describe_user_result: OperationResult = OperationResult.success(
            data={"UserId": "user-123", "UserName": "alice@example.com"}
        )
        self.user_lookup_result: OperationResult = OperationResult.success(
            data={"UserId": "user-123"}
        )
        self.create_user_result: OperationResult = OperationResult.success(
            data={"UserId": "user-123"}
        )
        self.membership_lookup_result: OperationResult = OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="membership not found",
            error_code="RESOURCE_NOT_FOUND",
        )
        self.create_membership_result: OperationResult = OperationResult.success()
        self.delete_membership_result: OperationResult = OperationResult.success()
        self.list_group_memberships_for_member_result: OperationResult = (
            OperationResult.success(data=[])
        )
        self.list_group_memberships_result: OperationResult = OperationResult.success(
            data=[]
        )
        self.list_groups_with_memberships_result: OperationResult = (
            OperationResult.success(data=[])
        )
        self.list_users_result: OperationResult = OperationResult.success(data=[])
        self.delete_user_result: OperationResult = OperationResult.success()

    def get_user_id_by_username(self, username: str) -> OperationResult:
        self.calls.append(("get_user_id_by_username", username))
        return self.user_lookup_result

    def describe_user_by_username(self, username: str) -> OperationResult:
        self.calls.append(("describe_user_by_username", username))
        return self.describe_user_result

    def create_user(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("create_user", kwargs))
        return self.create_user_result

    def get_group_membership_id(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("get_group_membership_id", kwargs))
        return self.membership_lookup_result

    def create_group_membership(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("create_group_membership", kwargs))
        return self.create_membership_result

    def delete_group_membership(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("delete_group_membership", kwargs))
        return self.delete_membership_result

    def list_group_memberships_for_member(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("list_group_memberships_for_member", kwargs))
        return self.list_group_memberships_for_member_result

    def list_group_memberships(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("list_group_memberships", kwargs))
        return self.list_group_memberships_result

    def list_users(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("list_users", kwargs))
        return self.list_users_result

    def list_groups_with_memberships(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("list_groups_with_memberships", kwargs))
        return self.list_groups_with_memberships_result

    def delete_user(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("delete_user", kwargs))
        return self.delete_user_result


class FakeAWSClients:
    """Minimal AWS clients facade for adapter tests."""

    def __init__(self, identitystore: FakeIdentityStoreClient) -> None:
        self.identitystore = identitystore


def make_adapter(client: FakeIdentityStoreClient) -> AwsIdentityCenterAdapter:
    """Create an adapter with a fake AWS facade."""
    return AwsIdentityCenterAdapter(cast(Any, FakeAWSClients(client)))


@pytest.mark.unit
def test_ensure_user_uses_username_lookup_instead_of_list_users() -> None:
    """User existence checks should use the dedicated username lookup helper."""
    client = FakeIdentityStoreClient()
    adapter = make_adapter(client)

    result = adapter.ensure_user("alice@example.com")

    assert result.is_success
    assert ("get_user_id_by_username", "alice@example.com") in client.calls
    assert all(call[0] != "list_users" for call in client.calls)


@pytest.mark.unit
def test_ensure_user_creates_when_identity_store_user_not_found() -> None:
    """ResourceNotFoundException from get_user_id should trigger user creation."""
    client = FakeIdentityStoreClient()
    client.user_lookup_result = OperationResult.error(
        OperationStatus.PERMANENT_ERROR,
        message="USER not found.",
        error_code="ResourceNotFoundException",
    )
    adapter = make_adapter(client)

    result = adapter.ensure_user("alice@example.com")

    assert result.is_success
    assert any(call[0] == "create_user" for call in client.calls)


@pytest.mark.unit
def test_ensure_user_create_payload_matches_identitystore_requirements() -> None:
    """CreateUser payload should include Name and canonical WORK email type."""
    client = FakeIdentityStoreClient()
    client.user_lookup_result = OperationResult.error(
        OperationStatus.PERMANENT_ERROR,
        message="USER not found.",
        error_code="ResourceNotFoundException",
    )
    adapter = make_adapter(client)

    result = adapter.ensure_user("sre-bot@cds-snc.ca")

    assert result.is_success
    create_calls = [call for call in client.calls if call[0] == "create_user"]
    assert len(create_calls) == 1
    payload = create_calls[0][1]
    assert payload["UserName"] == "sre-bot@cds-snc.ca"
    assert payload["DisplayName"] == "Sre Bot"
    assert payload["Name"] == {"GivenName": "Sre", "FamilyName": "Bot"}
    assert payload["Emails"] == [
        {"Value": "sre-bot@cds-snc.ca", "Primary": True, "Type": "WORK"}
    ]


@pytest.mark.unit
def test_get_user_uses_describe_user_by_username() -> None:
    """Direct user lookups should reuse the infrastructure client describe method."""
    client = FakeIdentityStoreClient()
    adapter = make_adapter(client)

    result = adapter.get_user("alice@example.com")

    assert result.is_success
    assert client.calls == [("describe_user_by_username", "alice@example.com")]


@pytest.mark.unit
def test_apply_entitlement_does_not_create_membership_when_lookup_fails() -> None:
    """Only NOT_FOUND should trigger membership creation."""
    client = FakeIdentityStoreClient()
    client.membership_lookup_result = OperationResult.error(
        OperationStatus.PERMANENT_ERROR,
        message="access denied",
        error_code="ACCESS_DENIED",
    )
    adapter = make_adapter(client)

    result = adapter.apply_entitlement("alice@example.com", "group", "group-123")

    assert not result.is_success
    assert result.error_code == "ACCESS_DENIED"
    assert all(call[0] != "create_group_membership" for call in client.calls)


@pytest.mark.unit
def test_list_all_provisioned_users_collects_primary_emails() -> None:
    """Primary emails should be normalized from the list_users client response."""
    client = FakeIdentityStoreClient()
    client.list_users_result = OperationResult.success(
        data=[
            {
                "UserId": "user-1",
                "Emails": [
                    {"Value": "Alice@example.com", "Primary": True},
                    {"Value": "alt@example.com", "Primary": False},
                ],
            },
            {
                "UserId": "user-2",
                "Emails": [{"Value": "Bob@example.com", "Primary": True}],
            },
        ]
    )
    adapter = make_adapter(client)

    result = adapter.list_all_provisioned_users()

    assert result.is_success
    assert result.data == {"alice@example.com", "bob@example.com"}


@pytest.mark.unit
def test_list_members_for_groups_uses_bulk_path() -> None:
    """Bulk group read should map GroupMemberships.UserDetails to email sets."""
    client = FakeIdentityStoreClient()
    client.list_groups_with_memberships_result = OperationResult.success(
        data=[
            {
                "GroupId": "group-1",
                "GroupMemberships": [
                    {
                        "MemberId": {"UserId": "u-1"},
                        "UserDetails": {
                            "UserId": "u-1",
                            "Emails": [
                                {
                                    "Value": "Alice@example.com",
                                    "Primary": True,
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "GroupId": "group-2",
                "GroupMemberships": [],
            },
        ]
    )
    adapter = make_adapter(client)

    result = adapter.list_members_for_groups({"group-1", "group-2"})

    assert result.is_success
    assert result.data == {
        "group-1": {"alice@example.com"},
        "group-2": set(),
    }
    assert any(call[0] == "list_groups_with_memberships" for call in client.calls)


@pytest.mark.unit
def test_list_members_for_groups_falls_back_when_bulk_fails() -> None:
    """Fallback should call list_group_members when bulk orchestration fails."""
    client = FakeIdentityStoreClient()
    client.list_groups_with_memberships_result = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="temporary failure",
        error_code="THROTTLED",
    )
    client.list_group_memberships_result = OperationResult.success(
        data=[
            {"MemberId": {"UserId": "u-1"}},
        ]
    )
    client.list_users_result = OperationResult.success(
        data=[
            {
                "UserId": "u-1",
                "Emails": [{"Value": "alice@example.com", "Primary": True}],
            }
        ]
    )
    adapter = make_adapter(client)

    result = adapter.list_members_for_groups({"group-1"})

    assert result.is_success
    assert result.data == {"group-1": {"alice@example.com"}}
    assert any(call[0] == "list_group_memberships" for call in client.calls)
