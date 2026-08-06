"""Unit tests for the AWS Identity Center access-sync adapter.

The adapter is injected with a typed boto3 ``identitystore`` client — never
an ``AWSClients`` facade. Fakes here are ``MagicMock(spec=...)`` instances
restricted to the real boto3 IdentityStore operation surface (plus
``get_paginator``), so any facade-only helper (e.g. ``list_groups_with_memberships``)
is absent by construction, matching production.
"""

from typing import Any
from unittest.mock import MagicMock, call

import pytest
from botocore.exceptions import ClientError

from packages.access.sync.adapters.aws_identity_center import (
    AwsIdentityCenterAdapter,
    normalize_group_name,
)

_IDENTITY_STORE_ID = "d-1234567890"

_IDENTITYSTORE_CLIENT_METHODS = [
    "list_users",
    "list_groups",
    "describe_group",
    "get_user_id",
    "create_user",
    "delete_user",
    "get_group_membership_id",
    "create_group_membership",
    "delete_group_membership",
    "list_group_memberships_for_member",
    "list_group_memberships",
    "get_paginator",
]

_DEFAULT_PAGES: dict[str, list[dict[str, Any]]] = {
    "list_users": [{"Users": []}],
    "list_groups": [{"Groups": []}],
    "list_group_memberships": [{"GroupMemberships": []}],
    "list_group_memberships_for_member": [{"GroupMemberships": []}],
}


def _client_error(operation: str, code: str = "ResourceNotFoundException", message: str = "not found") -> ClientError:
    return ClientError(error_response={"Error": {"Code": code, "Message": message}}, operation_name=operation)


def _configure_paginated(client: MagicMock, **overrides: list[dict[str, Any]] | ClientError) -> None:
    """Wire ``client.get_paginator(op).paginate(...)`` per operation.

    Each override is either a list of pages to return, or a ``ClientError``
    to raise when ``paginate(...)`` is invoked.
    """
    pages_by_op: dict[str, Any] = {**_DEFAULT_PAGES, **overrides}
    paginators: dict[str, MagicMock] = {}
    for op, value in pages_by_op.items():
        paginator = MagicMock()
        if isinstance(value, Exception):
            paginator.paginate.side_effect = value
        else:
            paginator.paginate.return_value = value
        paginators[op] = paginator
    client.get_paginator.side_effect = lambda operation_name: paginators[operation_name]


def make_client() -> MagicMock:
    """Build a typed-boto3-identitystore-shaped mock restricted to the real operation surface."""
    client = MagicMock(spec=_IDENTITYSTORE_CLIENT_METHODS)
    client.describe_group.side_effect = _client_error("DescribeGroup")
    client.get_group_membership_id.side_effect = _client_error("GetGroupMembershipId")
    client.get_user_id.return_value = {"UserId": "user-123"}
    client.create_user.return_value = {"UserId": "user-123"}
    client.create_group_membership.return_value = {"MembershipId": "membership-123"}
    client.delete_group_membership.return_value = {}
    client.delete_user.return_value = {}
    _configure_paginated(client)
    return client


def make_adapter(client: MagicMock) -> AwsIdentityCenterAdapter:
    """Create an adapter with a typed identitystore client — no facade."""
    return AwsIdentityCenterAdapter(identitystore=client, identity_store_id=_IDENTITY_STORE_ID)


@pytest.mark.unit
def test_ensure_user_uses_username_lookup_instead_of_list_users() -> None:
    """User existence checks should use GetUserId, not a full ListUsers scan."""
    client = make_client()
    adapter = make_adapter(client)

    result = adapter.ensure_user("alice@example.com")

    assert result.is_success
    assert client.get_user_id.called
    alternate_identifier = client.get_user_id.call_args.kwargs["AlternateIdentifier"]
    assert alternate_identifier["UniqueAttribute"]["AttributeValue"] == "alice@example.com"
    assert not client.list_users.called


@pytest.mark.unit
def test_ensure_user_passes_identity_store_id_to_get_user_id() -> None:
    """Every call must be scoped to the configured Identity Store ID."""
    client = make_client()
    adapter = make_adapter(client)

    adapter.ensure_user("alice@example.com")

    assert client.get_user_id.call_args.kwargs["IdentityStoreId"] == _IDENTITY_STORE_ID


@pytest.mark.unit
def test_ensure_user_creates_when_identity_store_user_not_found() -> None:
    """ResourceNotFoundException from GetUserId should trigger user creation."""
    client = make_client()
    client.get_user_id.side_effect = _client_error("GetUserId")
    adapter = make_adapter(client)

    result = adapter.ensure_user("alice@example.com")

    assert result.is_success
    assert client.create_user.called


@pytest.mark.unit
def test_ensure_user_create_payload_matches_identitystore_requirements() -> None:
    """CreateUser payload should include Name and canonical WORK email type."""
    client = make_client()
    client.get_user_id.side_effect = _client_error("GetUserId")
    adapter = make_adapter(client)

    result = adapter.ensure_user("sre-bot@cds-snc.ca")

    assert result.is_success
    assert client.create_user.call_count == 1
    payload = client.create_user.call_args.kwargs
    assert payload["UserName"] == "sre-bot@cds-snc.ca"
    assert payload["DisplayName"] == "Sre Bot"
    assert payload["Name"] == {"GivenName": "Sre", "FamilyName": "Bot"}
    assert payload["Emails"] == [{"Value": "sre-bot@cds-snc.ca", "Primary": True, "Type": "WORK"}]


@pytest.mark.unit
def test_apply_entitlement_does_not_create_membership_when_lookup_fails() -> None:
    """Only NOT_FOUND should trigger membership creation; other errors propagate."""
    client = make_client()
    client.get_group_membership_id.side_effect = _client_error(
        "GetGroupMembershipId", code="AccessDeniedException", message="access denied"
    )
    client.describe_group.return_value = {"GroupId": "11111111-2222-3333-4444-555555555555"}
    adapter = make_adapter(client)

    result = adapter.apply_entitlement(
        "alice@example.com",
        "group",
        "11111111-2222-3333-4444-555555555555",
    )

    assert not result.is_success
    assert result.error_code == "AccessDeniedException"
    assert not client.create_group_membership.called


@pytest.mark.unit
def test_remove_entitlement_reports_already_absent_when_not_member() -> None:
    """GetGroupMembershipId NOT_FOUND should be treated as an idempotent no-op."""
    client = make_client()
    client.describe_group.return_value = {"GroupId": "11111111-2222-3333-4444-555555555555"}
    adapter = make_adapter(client)

    result = adapter.remove_entitlement(
        "alice@example.com",
        "group",
        "11111111-2222-3333-4444-555555555555",
    )

    assert result.is_success
    assert result.message == "group_membership_already_absent"
    assert not client.delete_group_membership.called


@pytest.mark.unit
def test_remove_user_reports_already_absent_when_user_not_found() -> None:
    """ResourceNotFoundException from GetUserId should be an idempotent no-op for remove_user."""
    client = make_client()
    client.get_user_id.side_effect = _client_error("GetUserId")
    adapter = make_adapter(client)

    result = adapter.remove_user("alice@example.com")

    assert result.is_success
    assert result.message == "user_already_absent"
    assert not client.delete_user.called


@pytest.mark.unit
def test_list_all_provisioned_users_collects_primary_emails() -> None:
    """Primary emails should be normalized from the paginated list_users response."""
    client = make_client()
    _configure_paginated(
        client,
        list_users=[
            {
                "Users": [
                    {
                        "UserId": "user-1",
                        "Emails": [
                            {"Value": "Alice@example.com", "Primary": True},
                            {"Value": "alt@example.com", "Primary": False},
                        ],
                    },
                ]
            },
            {
                "Users": [
                    {
                        "UserId": "user-2",
                        "Emails": [{"Value": "bob@example.com", "Primary": True}],
                    },
                ]
            },
        ],
    )
    adapter = make_adapter(client)

    result = adapter.list_all_provisioned_users()

    assert result.is_success
    assert result.data == {"alice@example.com", "bob@example.com"}
    client.get_paginator.assert_any_call("list_users")


@pytest.mark.unit
def test_list_members_for_groups_always_uses_per_group_fallback() -> None:
    """The typed client has no ``list_groups_with_memberships`` helper.

    Unlike the legacy facade, the real boto3 IdentityStore client does not
    expose a bulk group-membership orchestration method, so the adapter must
    always resolve members via the per-group ``list_group_memberships`` path.
    """
    client = make_client()
    group_1_id = "11111111-2222-3333-4444-555555555555"
    client.describe_group.return_value = {"GroupId": group_1_id}
    _configure_paginated(
        client,
        list_group_memberships=[{"GroupMemberships": [{"MemberId": {"UserId": "u-1"}}]}],
        list_users=[{"Users": [{"UserId": "u-1", "Emails": [{"Value": "alice@example.com", "Primary": True}]}]}],
    )
    adapter = make_adapter(client)

    result = adapter.list_members_for_groups({group_1_id})

    assert result.is_success
    assert result.data == {group_1_id: {"alice@example.com"}}
    assert not hasattr(client, "list_groups_with_memberships")
    client.get_paginator.assert_any_call("list_group_memberships")


@pytest.mark.unit
def test_apply_entitlement_resolves_group_name_to_group_id() -> None:
    """Group-name entitlement IDs should resolve via the group index."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("team1-prd-admin", "resolved-group-id"))}])
    adapter = make_adapter(client)

    result = adapter.apply_entitlement(
        "alice@example.com",
        "group",
        "team1-prd-admin",
    )

    assert result.is_success
    assert client.create_group_membership.call_args.kwargs["GroupId"] == "resolved-group-id"


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
    client = make_client()
    group_id = "11111111-2222-3333-4444-555555555555"
    client.describe_group.return_value = {"GroupId": group_id, "DisplayName": "Admin"}
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", group_id)

    assert result.is_success
    assert result.data == group_id
    # list_groups should NOT have been called for UUID resolution
    assert not client.list_groups.called


@pytest.mark.unit
def test_resolve_group_id_exact_display_name() -> None:
    """A token that exactly matches an AWS IC display name resolves via the index."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("admin", "group-admin-id"))}])
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "admin")

    assert result.is_success
    assert result.data == "group-admin-id"


@pytest.mark.unit
def test_resolve_group_id_non_uuid_skips_describe_group() -> None:
    """Display-name tokens should not trigger describe_group UUID validation calls."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("scratch", "group-scratch-id"))}])
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "scratch")

    assert result.is_success
    assert result.data == "group-scratch-id"
    assert not client.describe_group.called


@pytest.mark.unit
def test_resolve_group_id_normalized_display_name() -> None:
    """A token whose casefold matches an AWS IC group resolves via the index."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("FinOps-ReadOnly", "group-finops-id"))}])
    adapter = make_adapter(client)

    # Token "finops-readonly" normalizes via casefold to "finops-readonly"
    # Group "FinOps-ReadOnly" normalizes to "finops-readonly" — should match
    result = adapter.canonicalize_entitlement_id("group", "finops-readonly")

    assert result.is_success
    assert result.data == "group-finops-id"


@pytest.mark.unit
def test_resolve_group_id_ambiguous_name_returns_error() -> None:
    """When normalized token matches multiple groups, AMBIGUOUS_GROUP_NAME is returned."""
    client = make_client()
    _configure_paginated(
        client,
        list_groups=[
            {
                "Groups": _make_group_list(
                    ("Admin", "group-admin-1"),
                    ("ADMIN", "group-admin-2"),
                )
            }
        ],
    )
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "admin")

    assert not result.is_success
    assert result.error_code == "AMBIGUOUS_GROUP_NAME"


@pytest.mark.unit
def test_resolve_group_id_not_found_returns_error() -> None:
    """When no group matches the token, GROUP_ID_NOT_FOUND is returned."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("other-group", "group-other-id"))}])
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "missing")

    assert not result.is_success
    assert result.error_code == "GROUP_ID_NOT_FOUND"


@pytest.mark.unit
def test_resolve_group_id_caches_result() -> None:
    """Repeated resolution of the same token should not re-call list_groups."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("admin", "group-cached-id"))}])
    adapter = make_adapter(client)

    result1 = adapter.canonicalize_entitlement_id("group", "admin")
    result2 = adapter.canonicalize_entitlement_id("group", "admin")

    assert result1.is_success and result2.is_success
    assert result1.data == result2.data == "group-cached-id"
    assert client.get_paginator.call_args_list.count(call("list_groups")) == 1


@pytest.mark.unit
def test_resolve_group_id_list_groups_failure_propagates() -> None:
    """If list_groups fails, the error propagates from canonicalize_entitlement_id."""
    client = make_client()
    _configure_paginated(client, list_groups=_client_error("ListGroups", code="ThrottlingException", message="throttled"))
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "admin")

    assert not result.is_success
    assert result.error_code == "ThrottlingException"


@pytest.mark.unit
def test_resolve_group_id_no_prefix_matches_full_slug() -> None:
    """Token passed directly (pre-stripped) resolves via exact display-name match."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("platform-admin", "group-platform-admin-id"))}])
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "platform-admin")

    assert result.is_success
    assert result.data == "group-platform-admin-id"


@pytest.mark.unit
def test_resolve_group_id_token_direct_lookup() -> None:
    """Pre-stripped token resolves directly without any prefix handling."""
    client = make_client()
    _configure_paginated(client, list_groups=[{"Groups": _make_group_list(("ops-team", "group-ops-id"))}])
    adapter = make_adapter(client)

    result = adapter.canonicalize_entitlement_id("group", "ops-team")

    assert result.is_success
    assert result.data == "group-ops-id"


# ---------------------------------------------------------------------------
# build_aws_identity_center_adapter() factory tests (AC#1, AC#5)
# ---------------------------------------------------------------------------


class _FakeAwsSettings:
    """Minimal AwsSettings stand-in for factory-wiring tests."""

    def __init__(self, instance_id: str, identitystore_role_arn: str) -> None:
        self.INSTANCE_ID = instance_id
        self.SERVICE_ROLE_MAP = {"identitystore": identitystore_role_arn}


@pytest.mark.unit
def test_build_aws_identity_center_adapter_wires_typed_client_no_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC#1: the factory must build the adapter from get_aws_client("identitystore"), not an AWSClients facade."""
    from packages.access.sync.adapters import aws_identity_center as module

    fake_client = make_client()
    fake_client.get_user_id.return_value = {"UserId": "user-123"}
    captured: dict[str, Any] = {}

    def _fake_get_aws_client(service_name: str, role_arn: str | None = None) -> MagicMock:
        captured["service_name"] = service_name
        return fake_client

    monkeypatch.setattr(module, "get_aws_client", _fake_get_aws_client)
    monkeypatch.setattr(
        module,
        "get_aws_settings",
        lambda: _FakeAwsSettings(instance_id="d-9876543210", identitystore_role_arn="arn:aws:iam::111111111111:role/org-role"),
    )

    adapter = module.build_aws_identity_center_adapter()

    assert isinstance(adapter, AwsIdentityCenterAdapter)
    assert captured["service_name"] == "identitystore"
    adapter.ensure_user("alice@example.com")
    assert fake_client.get_user_id.call_args.kwargs["IdentityStoreId"] == "d-9876543210"


@pytest.mark.unit
def test_build_aws_identity_center_adapter_assumes_org_role_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC#5: identitystore must be assumed under SERVICE_ROLE_MAP's org role, not the bot's own credentials."""
    from packages.access.sync.adapters import aws_identity_center as module

    captured: dict[str, Any] = {}

    def _fake_get_aws_client(service_name: str, role_arn: str | None = None) -> MagicMock:
        captured["role_arn"] = role_arn
        return make_client()

    monkeypatch.setattr(module, "get_aws_client", _fake_get_aws_client)
    monkeypatch.setattr(
        module,
        "get_aws_settings",
        lambda: _FakeAwsSettings(instance_id="d-9876543210", identitystore_role_arn="arn:aws:iam::111111111111:role/org-role"),
    )

    module.build_aws_identity_center_adapter()

    assert captured["role_arn"] == "arn:aws:iam::111111111111:role/org-role"


@pytest.mark.unit
def test_build_aws_identity_center_adapter_omits_role_arn_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """When SERVICE_ROLE_MAP has no identitystore role configured, role_arn must be None.

    Prevents a spurious STS AssumeRole call with an empty-string RoleArn in
    default/test configuration.
    """
    from packages.access.sync.adapters import aws_identity_center as module

    captured: dict[str, Any] = {}

    def _fake_get_aws_client(service_name: str, role_arn: str | None = None) -> MagicMock:
        captured["role_arn"] = role_arn
        return make_client()

    monkeypatch.setattr(module, "get_aws_client", _fake_get_aws_client)
    monkeypatch.setattr(
        module,
        "get_aws_settings",
        lambda: _FakeAwsSettings(instance_id="d-9876543210", identitystore_role_arn=""),
    )

    module.build_aws_identity_center_adapter()

    assert captured["role_arn"] is None
