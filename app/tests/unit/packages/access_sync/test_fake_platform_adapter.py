"""Unit tests for fake non-AWS access sync adapter."""

import pytest

from infrastructure.operations import OperationStatus
from packages.access_sync.adapters.fake_platform import FakePlatformAdapter


@pytest.mark.unit
def test_fake_adapter_has_deterministic_seed_data():
    """Adapter should expose sample users and group memberships."""
    # Arrange
    adapter = FakePlatformAdapter()

    # Act
    users_result = adapter.list_all_provisioned_users()
    group_result = adapter.list_group_members("fake-group-admin")

    # Assert
    assert users_result.is_success
    assert users_result.data == {
        "alice@example.com",
        "bob@example.com",
        "carol@example.com",
    }
    assert group_result.is_success
    assert group_result.data == {"alice@example.com", "carol@example.com"}


@pytest.mark.unit
def test_fake_adapter_apply_and_remove_group_entitlement_updates_state():
    """Applying/removing group entitlement should change current entitlement IDs."""
    # Arrange
    adapter = FakePlatformAdapter()
    user_email = "dana@example.com"
    group_id = "fake-group-read"

    # Act
    apply_result = adapter.apply_entitlement(
        user_email=user_email,
        entitlement_type="group",
        entitlement_id=group_id,
    )
    current_after_apply = adapter.get_current_entitlement_ids(user_email)
    remove_result = adapter.remove_entitlement(
        user_email=user_email,
        entitlement_type="group",
        entitlement_id=group_id,
    )
    current_after_remove = adapter.get_current_entitlement_ids(user_email)

    # Assert
    assert apply_result.is_success
    assert current_after_apply.is_success
    assert current_after_apply.data == {group_id}
    assert remove_result.is_success
    assert current_after_remove.is_success
    assert current_after_remove.data == set()


@pytest.mark.unit
def test_fake_adapter_get_user_not_found_returns_normalized_error():
    """Unknown users should return NOT_FOUND with a stable error code."""
    # Arrange
    adapter = FakePlatformAdapter()

    # Act
    result = adapter.get_user("missing@example.com")

    # Assert
    assert not result.is_success
    assert result.status == OperationStatus.NOT_FOUND
    assert result.error_code == "USER_NOT_FOUND"
