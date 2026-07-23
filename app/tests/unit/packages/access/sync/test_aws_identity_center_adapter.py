"""Unit tests for the AWS Identity Center access-sync adapter."""

from typing import Any, cast

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.adapters.aws_identity_center import (
    AwsIdentityCenterAdapter,
    normalize_group_name,
)


class FakeIdentityStoreClient:
    """Minimal Identity Store client test double."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.describe_user_result: OperationResult = OperationResult.success(
            data={"UserId": "user-123", "UserName": "alice@example.com"}
        )
        self.user_lookup_result: OperationResult = OperationResult.success(data={"UserId": "user-123"})
        self.create_user_result: OperationResult = OperationResult.success(data={"UserId": "user-123"})
        self.membership_lookup_result: OperationResult = OperationResult.error(
            OperationStatus.NOT_FOUND,
            message="membership not found",
            error_code="RESOURCE_NOT_FOUND",
        )
        self.create_membership_result: OperationResult = OperationResult.success()
        self.delete_membership_result: OperationResult = OperationResult.success()
        self.list_group_memberships_for_member_result: OperationResult = OperationResult.success(data=[])
        self.list_group_memberships_result: OperationResult = OperationResult.success(data=[])
        self.describe_group_result: OperationResult = OperationResult.success(data={})
        self.get_group_id_by_group_name_result: OperationResult = OperationResult.success(data={"GroupId": "group-123"})
        self.list_groups_with_memberships_result: OperationResult = OperationResult.success(data=[])
        self.list_groups_result: OperationResult = OperationResult.success(data=[])
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

    def describe_group(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("describe_group", kwargs))
        return self.describe_group_result

    def get_group_id_by_group_name(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("get_group_id_by_group_name", kwargs))
        return self.get_group_id_by_group_name_result

    def list_users(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("list_users", kwargs))
        return self.list_users_result

    def list_groups_with_memberships(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("list_groups_with_memberships", kwargs))
        return self.list_groups_with_memberships_result

    def list_groups(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("list_groups", kwargs))
        return self.list_groups_result

    def delete_user(self, **kwargs: Any) -> OperationResult:
        self.calls.append(("delete_user", kwargs))
        return self.delete_user_result


class FakeAWSClients:
    """Minimal AWS clients facade for adapter tests."""

    def __init__(self, identitystore: FakeIdentityStoreClient) -> None:
        self.identitystore = identitystore


def make_adapter(
    client: FakeIdentityStoreClient,
) -> AwsIdentityCenterAdapter:
    """Create an adapter with a fake AWS facade."""
    return AwsIdentityCenterAdapter(
        cast(Any, FakeAWSClients(client)),
    )


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
    assert payload["Emails"] == [{"Value": "sre-bot@cds-snc.ca", "Primary": True, "Type": "WORK"}]


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

    result = adapter.apply_entitlement(
        "alice@example.com",
        "group",
        "11111111-2222-3333-4444-555555555555",
    )

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
                "Emails": [
                    {"Value": "bob@example.com", "Primary": True},
                ],
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
    group_1_id = "11111111-2222-3333-4444-555555555555"
    group_2_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    client.list_groups_with_memberships_result = OperationResult.success(
        data=[
            {
                "GroupId": group_1_id,
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
                "GroupId": group_2_id,
                "GroupMemberships": [],
            },
        ]
    )
    adapter = make_adapter(client)

    result = adapter.list_members_for_groups({group_1_id, group_2_id})

    assert result.is_success
    assert result.data == {
        group_1_id: {"alice@example.com"},
        group_2_id: set(),
    }
    assert any(call[0] == "list_groups_with_memberships" for call in client.calls)


@pytest.mark.unit
def test_list_members_for_groups_falls_back_when_bulk_fails() -> None:
    """Fallback should call list_group_members when bulk orchestration fails."""
    client = FakeIdentityStoreClient()
    group_1_id = "11111111-2222-3333-4444-555555555555"
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

    result = adapter.list_members_for_groups({group_1_id})

    assert result.is_success
    assert result.data == {group_1_id: {"alice@example.com"}}
    assert any(call[0] == "list_group_memberships" for call in client.calls)


@pytest.mark.unit
def test_list_members_for_groups_bulk_resolves_member_ids_without_user_details() -> None:
    """Bulk group read should resolve MemberId.UserId when UserDetails is omitted."""
    client = FakeIdentityStoreClient()
    group_1_id = "11111111-2222-3333-4444-555555555555"
    client.list_groups_with_memberships_result = OperationResult.success(
        data=[
            {
                "GroupId": group_1_id,
                "GroupMemberships": [
                    {"MemberId": {"UserId": "u-1"}},
                    {"MemberId": {"UserId": "u-2"}},
                ],
            }
        ]
    )
    client.list_users_result = OperationResult.success(
        data=[
            {
                "UserId": "u-1",
                "Emails": [{"Value": "Alice@example.com", "Primary": True}],
            },
            {
                "UserId": "u-2",
                "Emails": [{"Value": "bob@example.com", "Primary": True}],
            },
        ]
    )
    adapter = make_adapter(client)

    result = adapter.list_members_for_groups({group_1_id})

    assert result.is_success
    assert result.data == {group_1_id: {"alice@example.com", "bob@example.com"}}
    assert any(call[0] == "list_groups_with_memberships" for call in client.calls)
    assert any(call[0] == "list_users" for call in client.calls)


@pytest.mark.unit
def test_apply_entitlement_resolves_group_name_to_group_id() -> None:
    """Group-name entitlement IDs should resolve via the group index."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(
        OperationStatus.NOT_FOUND,
        message="group id not found",
        error_code="GROUP_NOT_FOUND",
    )
    client.list_groups_result = OperationResult.success(data=_make_group_list(("team1-prd-admin", "resolved-group-id")))
    adapter = make_adapter(client)

    result = adapter.apply_entitlement(
        "alice@example.com",
        "group",
        "team1-prd-admin",
    )

    assert result.is_success
    create_call = next(call for call in client.calls if call[0] == "create_group_membership")
    assert create_call[1]["GroupId"] == "resolved-group-id"


# ---------------------------------------------------------------------------
# Module-level helper tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_normalize_group_name_strips_and_casesfolds() -> None:
    assert normalize_group_name("  Admin  ") == "admin"
    assert normalize_group_name("SG-AWS-FinOps") == "sg-aws-finops"
    assert normalize_group_name("ec2-ReadOnly") == "ec2-readonly"


# ---------------------------------------------------------------------------
# Group index resolution tests
# ---------------------------------------------------------------------------


def _make_group_list(*name_id_pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"GroupId": gid, "DisplayName": name} for name, gid in name_id_pairs]


@pytest.mark.unit
def test_resolve_group_id_uuid_passthrough() -> None:
    """A UUID that describe_group confirms should be returned as-is without index."""
    client = FakeIdentityStoreClient()
    group_id = "11111111-2222-3333-4444-555555555555"
    client.describe_group_result = OperationResult.success(data={"GroupId": group_id, "DisplayName": "Admin"})
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", group_id)

    assert result.is_success
    assert result.data == group_id
    # list_groups should NOT have been called for UUID resolution
    assert all(call[0] != "list_groups" for call in client.calls)


@pytest.mark.unit
def test_resolve_group_id_exact_display_name() -> None:
    """A token that exactly matches an AWS IC display name resolves via the index."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.success(data=_make_group_list(("admin", "group-admin-id")))
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "admin")

    assert result.is_success
    assert result.data == "group-admin-id"


@pytest.mark.unit
def test_resolve_group_id_non_uuid_skips_describe_group() -> None:
    """Display-name tokens should not trigger describe_group UUID validation calls."""
    client = FakeIdentityStoreClient()
    client.list_groups_result = OperationResult.success(data=_make_group_list(("scratch", "group-scratch-id")))
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "scratch")

    assert result.is_success
    assert result.data == "group-scratch-id"
    assert all(call[0] != "describe_group" for call in client.calls)


@pytest.mark.unit
def test_resolve_group_id_normalized_display_name() -> None:
    """A token whose casefold matches an AWS IC group resolves via the index."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.success(data=_make_group_list(("FinOps-ReadOnly", "group-finops-id")))
    adapter = make_adapter(client)

    # Token "finops-readonly" normalizes via casefold to "finops-readonly"
    # Group "FinOps-ReadOnly" normalizes to "finops-readonly" — should match
    result = adapter.canonicalize_entitlement_id("group", "finops-readonly")

    assert result.is_success
    assert result.data == "group-finops-id"


@pytest.mark.unit
def test_resolve_group_id_ambiguous_name_returns_error() -> None:
    """When normalized token matches multiple groups, AMBIGUOUS_GROUP_NAME is returned."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.success(
        data=_make_group_list(
            ("Admin", "group-admin-1"),
            ("ADMIN", "group-admin-2"),
        )
    )
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "admin")

    assert not result.is_success
    assert result.error_code == "AMBIGUOUS_GROUP_NAME"


@pytest.mark.unit
def test_resolve_group_id_not_found_returns_error() -> None:
    """When no group matches the token, GROUP_ID_NOT_FOUND is returned."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.success(data=_make_group_list(("other-group", "group-other-id")))
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "missing")

    assert not result.is_success
    assert result.error_code == "GROUP_ID_NOT_FOUND"


@pytest.mark.unit
def test_resolve_group_id_caches_result() -> None:
    """Repeated resolution of the same token should not re-call list_groups."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.success(data=_make_group_list(("admin", "group-cached-id")))
    adapter = make_adapter(client)

    result1 = adapter.canonicalize_entitlement_id("group", "admin")
    result2 = adapter.canonicalize_entitlement_id("group", "admin")

    assert result1.is_success and result2.is_success
    assert result1.data == result2.data == "group-cached-id"
    assert sum(1 for call in client.calls if call[0] == "list_groups") == 1


@pytest.mark.unit
def test_resolve_group_id_list_groups_failure_propagates() -> None:
    """If list_groups fails, the error propagates from canonicalize_entitlement_id."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="throttled",
        error_code="THROTTLED",
    )
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "admin")

    assert not result.is_success
    assert result.error_code == "THROTTLED"


@pytest.mark.unit
def test_resolve_group_id_no_prefix_matches_full_slug() -> None:
    """Token passed directly (pre-stripped) resolves via exact display-name match."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.success(data=_make_group_list(("platform-admin", "group-platform-admin-id")))
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "platform-admin")

    assert result.is_success
    assert result.data == "group-platform-admin-id"


@pytest.mark.unit
def test_resolve_group_id_token_direct_lookup() -> None:
    """Pre-stripped token resolves directly without any prefix handling."""
    client = FakeIdentityStoreClient()
    client.describe_group_result = OperationResult.error(OperationStatus.NOT_FOUND, message="not found", error_code="NOT_FOUND")
    client.list_groups_result = OperationResult.success(data=_make_group_list(("ops-team", "group-ops-id")))
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "ops-team")

    assert result.is_success
    assert result.data == "group-ops-id"
