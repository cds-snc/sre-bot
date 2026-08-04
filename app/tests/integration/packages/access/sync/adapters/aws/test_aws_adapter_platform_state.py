"""Integration tests for AwsIdentityCenterAdapter platform-state methods.

Mocks are applied at the IdentityStoreClient facade level so the full
adapter logic (user-ID resolution, membership listing, error mapping) runs
against real code.

Scenarios covered:

  B1  ``_assess_live`` for a user that exists with no groups
      → must return AdapterAssessment(platform_user_exists=True, current_entitlement_ids=set()).
      Critical regression case: zero groups must not be treated as NOT_FOUND.

  B2  ``_assess_live`` for a user with group memberships
      → returns AdapterAssessment with correct group IDs.

  B3  ``_assess_live`` for a user absent from Identity Store
      → returns AdapterAssessment(platform_user_exists=False, current_entitlement_ids=set()).

  B4  ``_assess_live`` when list_group_memberships returns a service error
      → error propagated, NOT silently mapped to NOT_FOUND.

  B5  ``_fetch_current_state`` returns the full state dict including group_ids.

  B6  ``list_group_memberships_for_member`` called with correct member_id format.
"""

import pytest

from infrastructure.operations import OperationResult, OperationStatus
from packages.access.sync.domain import AdapterAssessment

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# B1: User exists with no groups — must return platform_user_exists=True
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_user_exists_true_when_user_has_no_group_memberships(
    make_aws_adapter,
):
    """
    Critical regression test.

    A user who exists in AWS Identity Store but belongs to zero IC groups
    must produce AdapterAssessment(platform_user_exists=True, current_entitlement_ids=set()).

    Returning platform_user_exists=False here would cause the coordinator to
    plan a spurious provision_user action.
    """
    adapter, _ = make_aws_adapter(
        user_id="ec5d2588-f081-70f2-db36-2afc4ef5ce94",
        group_memberships=[],
    )

    result = adapter._assess_live("test.user@example.com")

    assert result.is_success, f"Expected success but got: {result.status!r} ({result.error_code!r})"
    assert isinstance(result.data, AdapterAssessment)
    assert result.data.platform_user_exists is True
    assert result.data.current_entitlement_ids == set()


# ---------------------------------------------------------------------------
# B2: User has group memberships — returns the group IDs
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_group_ids_when_user_has_group_memberships(make_aws_adapter):
    group_id_a = "aaaa1111-0000-0000-0000-000000000001"
    group_id_b = "bbbb2222-0000-0000-0000-000000000002"
    adapter, _ = make_aws_adapter(
        user_id="some-user-uuid",
        group_memberships=[
            {"GroupId": group_id_a},
            {"GroupId": group_id_b},
        ],
    )

    result = adapter._assess_live("alice@example.com")

    assert result.is_success
    assert isinstance(result.data, AdapterAssessment)
    assert result.data.platform_user_exists is True
    assert result.data.current_entitlement_ids == {group_id_a, group_id_b}


# ---------------------------------------------------------------------------
# B3: User absent from Identity Store → platform_user_exists=False
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_user_exists_false_when_user_absent(make_aws_adapter):
    adapter, _ = make_aws_adapter(user_id=None)

    result = adapter._assess_live("ghost@example.com")

    assert result.is_success
    assert isinstance(result.data, AdapterAssessment)
    assert result.data.platform_user_exists is False
    assert result.data.current_entitlement_ids == set()


# ---------------------------------------------------------------------------
# B4: list_group_memberships service error → propagated, not silenced
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_propagate_service_error_from_list_group_memberships(make_aws_adapter):
    """A transient error must NOT be silently converted to NOT_FOUND."""
    service_error: OperationResult[None] = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="Service unavailable",
        error_code="SERVICE_UNAVAILABLE",
    )
    adapter, _ = make_aws_adapter(
        user_id="some-user-uuid",
        list_memberships_error=service_error,
    )

    result = adapter._assess_live("alice@example.com")

    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR


# ---------------------------------------------------------------------------
# B5: _fetch_current_state returns state dict with group_ids
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fetch_current_state_returns_user_id_and_empty_group_list(make_aws_adapter):
    user_id = "ec5d2588-f081-70f2-db36-2afc4ef5ce94"
    adapter, _ = make_aws_adapter(user_id=user_id, group_memberships=[])

    result = adapter._fetch_current_state("test.user@example.com")

    assert result.is_success
    assert result.data["user_id"] == user_id
    assert result.data["group_ids"] == []


# ---------------------------------------------------------------------------
# B6: list_group_memberships_for_member called with correct member_id format
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_list_group_memberships_called_with_user_id_format(make_aws_adapter):
    """list_group_memberships_for_member must receive {"UserId": ...} as member_id."""
    user_id = "ec5d2588-f081-70f2-db36-2afc4ef5ce94"
    adapter, fake_identitystore = make_aws_adapter(
        user_id=user_id,
        group_memberships=[],
    )

    adapter._assess_live("test.user@example.com")

    call_args = fake_identitystore.list_group_memberships_for_member.call_args
    assert call_args is not None
    member_id = call_args.kwargs.get("member_id") or call_args.args[0]
    assert member_id == {"UserId": user_id}


@pytest.mark.integration
def test_list_members_for_groups_bulk_resolves_member_ids_without_user_details(
    make_aws_adapter,
):
    """Bulk membership reads should map MemberId.UserId to emails when UserDetails is missing."""
    group_id = "11111111-2222-3333-4444-555555555555"
    adapter, fake_identitystore = make_aws_adapter()

    fake_identitystore.describe_group.return_value = OperationResult.success(data={"GroupId": group_id})
    fake_identitystore.list_groups_with_memberships.return_value = OperationResult.success(
        data=[
            {
                "GroupId": group_id,
                "GroupMemberships": [
                    {"MemberId": {"UserId": "u-1"}},
                    {"MemberId": {"UserId": "u-2"}},
                ],
            }
        ]
    )
    fake_identitystore.list_users.return_value = OperationResult.success(
        data=[
            {
                "UserId": "u-1",
                "Emails": [{"Value": "alice@example.com", "Primary": True}],
            },
            {
                "UserId": "u-2",
                "Emails": [{"Value": "bob@example.com", "Primary": True}],
            },
        ]
    )

    result = adapter.list_members_for_groups({group_id})

    assert result.is_success
    assert result.data == {group_id: {"alice@example.com", "bob@example.com"}}
