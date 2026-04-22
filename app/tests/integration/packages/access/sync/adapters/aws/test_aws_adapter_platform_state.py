"""Integration tests for AwsIdentityCenterAdapter platform-state methods.

Mocks are applied at the ``IdentityStoreClient`` facade level so the full
adapter logic (user-ID resolution, membership listing, error mapping) runs
against real code.

Scenarios covered:

  B1  ``get_current_entitlement_ids`` for a user that exists with no groups
      → must return ``OperationResult.success(data=set())``, NOT NOT_FOUND.
      This is the critical regression case: a user with zero group memberships
      must still be recognised as existing on the platform.

  B2  ``get_current_entitlement_ids`` for a user with group memberships
      → returns the set of GroupIds.

  B3  ``get_current_entitlement_ids`` for a user absent from Identity Store
      → returns NOT_FOUND (expected control flow, not an error).

  B4  ``get_current_entitlement_ids`` when ``list_group_memberships_for_member``
      returns a service error (not NOT_FOUND) → error propagated, not silently
      mapped to NOT_FOUND.

  B5  ``_fetch_current_state`` returns the full state dict including group_ids.

  B6  ``get_current_entitlement_ids`` called after ``_fetch_current_state`` on
      the same user → result is consistent.
"""

import pytest

from infrastructure.operations import OperationResult, OperationStatus

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# B1: User exists with no groups — must NOT return NOT_FOUND
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_empty_set_when_user_exists_with_no_group_memberships(
    make_aws_adapter,
):
    """
    Critical regression test.

    A user who exists in AWS Identity Store but belongs to zero IC groups
    must produce ``OperationResult.success(data=set())``.

    Returning NOT_FOUND here would cause the coordinator to treat the user
    as absent and plan a spurious ``provision_user`` action.
    """
    # Arrange — user exists, no group memberships
    adapter, _ = make_aws_adapter(
        user_id="ec5d2588-f081-70f2-db36-2afc4ef5ce94",
        group_memberships=[],
    )

    # Act
    result = adapter.get_current_entitlement_ids("test.user@example.com")

    # Assert
    assert (
        result.is_success
    ), f"Expected success but got: {result.status!r} ({result.error_code!r})"
    assert result.data == set(), f"Expected empty set but got: {result.data!r}"


# ---------------------------------------------------------------------------
# B2: User has group memberships — returns the group IDs
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_group_ids_when_user_has_group_memberships(
    make_aws_adapter,
):
    """User with two IC group memberships → both GroupIds in the returned set."""
    # Arrange
    group_id_a = "aaaa1111-0000-0000-0000-000000000001"
    group_id_b = "bbbb2222-0000-0000-0000-000000000002"
    adapter, _ = make_aws_adapter(
        user_id="some-user-uuid",
        group_memberships=[
            {"GroupId": group_id_a},
            {"GroupId": group_id_b},
        ],
    )

    # Act
    result = adapter.get_current_entitlement_ids("alice@example.com")

    # Assert
    assert result.is_success
    assert result.data == {group_id_a, group_id_b}


# ---------------------------------------------------------------------------
# B3: User absent from Identity Store → NOT_FOUND
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_return_not_found_when_user_absent_from_identity_store(
    make_aws_adapter,
):
    """Absent user → NOT_FOUND (expected; coordinator treats this as absent)."""
    # Arrange
    adapter, _ = make_aws_adapter(user_id=None)

    # Act
    result = adapter.get_current_entitlement_ids("ghost@example.com")

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.NOT_FOUND


# ---------------------------------------------------------------------------
# B4: list_group_memberships service error → propagated, not silenced
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_should_propagate_service_error_from_list_group_memberships(
    make_aws_adapter,
):
    """A transient error from list_group_memberships must NOT be mapped to NOT_FOUND.

    If the error were silently converted to NOT_FOUND the coordinator would
    plan a provision_user for a user that already exists, resulting in a
    duplicate-create attempt.
    """
    # Arrange
    service_error = OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="Service unavailable",
        error_code="SERVICE_UNAVAILABLE",
    )
    adapter, _ = make_aws_adapter(
        user_id="some-user-uuid",
        list_memberships_error=service_error,
    )

    # Act
    result = adapter.get_current_entitlement_ids("alice@example.com")

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR


# ---------------------------------------------------------------------------
# B5: _fetch_current_state returns state dict with group_ids
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_fetch_current_state_returns_user_id_and_empty_group_list(
    make_aws_adapter,
):
    """``_fetch_current_state`` must return success with group_ids=[] for a user
    that exists but has no groups — parallel assertion to B1."""
    # Arrange
    user_id = "ec5d2588-f081-70f2-db36-2afc4ef5ce94"
    adapter, _ = make_aws_adapter(user_id=user_id, group_memberships=[])

    # Act
    result = adapter._fetch_current_state("test.user@example.com")

    # Assert
    assert result.is_success
    assert result.data["user_id"] == user_id
    assert result.data["group_ids"] == []


# ---------------------------------------------------------------------------
# B6: list_group_memberships_for_member called with correct member_id format
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_list_group_memberships_called_with_user_id_format(
    make_aws_adapter,
):
    """``list_group_memberships_for_member`` must receive ``{"UserId": ...}``
    as the member_id — not a bare string or email."""
    # Arrange
    user_id = "ec5d2588-f081-70f2-db36-2afc4ef5ce94"
    adapter, fake_identitystore = make_aws_adapter(
        user_id=user_id,
        group_memberships=[],
    )

    # Act
    adapter.get_current_entitlement_ids("test.user@example.com")

    # Assert
    call_args = fake_identitystore.list_group_memberships_for_member.call_args
    assert call_args is not None
    member_id = call_args.kwargs.get("member_id") or call_args.args[0]
    assert member_id == {"UserId": user_id}
