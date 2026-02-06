"""Unit tests for AWS Identity Center synchronization handler."""

import pytest
from unittest.mock import patch

from modules.aws import identity_center


@pytest.fixture
def mock_google_groups():
    """Factory for creating Google groups."""

    def _make(count: int = 1):
        groups = []
        for i in range(count):
            groups.append(
                {
                    "name": f"AWS-Group{i}",
                    "email": f"aws-group{i}@example.com",
                    "members": [
                        {"primaryEmail": f"user{i}@example.com"},
                        {"primaryEmail": f"user{i+1}@example.com"},
                    ],
                }
            )
        return groups

    return _make


@pytest.fixture
def mock_aws_groups():
    """Factory for creating AWS Identity Center groups."""

    def _make(count: int = 1):
        groups = []
        for i in range(count):
            groups.append(
                {
                    "GroupId": f"group-{i}",
                    "DisplayName": f"Group{i}",
                    "GroupMemberships": [
                        {"MemberId": {"UserId": f"user{i}"}},
                    ],
                }
            )
        return groups

    return _make


@pytest.fixture
def mock_users():
    """Factory for creating users."""

    def _make(count: int = 1):
        users = []
        for i in range(count):
            users.append(
                {
                    "primaryEmail": f"user{i}@example.com",
                    "name": {
                        "givenName": f"User{i}",
                        "familyName": "Test",
                    },
                }
            )
        return users

    return _make


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_synchronize_users_and_groups_with_defaults(
    mock_sync_groups,
    mock_sync_users,
    mock_identity_store,
    mock_filters,
    mock_groups,
):
    """Test synchronize calls both user and group sync."""
    # Arrange
    mock_groups.get_groups_from_integration.side_effect = [
        [{"name": "AWS-Group1", "members": []}],  # source groups
        [{"DisplayName": "Group1", "GroupMemberships": []}],  # target groups
    ]
    mock_filters.get_unique_nested_dicts.return_value = []
    mock_identity_store.list_users.return_value = []
    mock_sync_users.return_value = ([], [])
    mock_sync_groups.return_value = ([], [])

    # Act
    result = identity_center.synchronize()

    # Assert
    assert result["users"] is not None
    assert result["groups"] is not None
    mock_sync_users.assert_called_once()
    mock_sync_groups.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_skip_user_sync_when_disabled(
    mock_sync_groups,
    mock_sync_users,
    mock_identity_store,
    mock_filters,
    mock_groups,
):
    """Test synchronize skips user sync when disabled."""
    # Arrange
    mock_groups.get_groups_from_integration.side_effect = [
        [{"name": "AWS-Group1", "members": []}],
        [{"DisplayName": "Group1", "GroupMemberships": []}],
    ]
    mock_filters.get_unique_nested_dicts.return_value = []
    mock_identity_store.list_users.return_value = []
    mock_sync_groups.return_value = ([], [])

    # Act
    identity_center.synchronize(enable_users_sync=False)

    # Assert
    mock_sync_users.assert_not_called()
    mock_sync_groups.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_skip_group_sync_when_disabled(
    mock_sync_groups,
    mock_sync_users,
    mock_identity_store,
    mock_filters,
    mock_groups,
):
    """Test synchronize skips group sync when disabled."""
    # Arrange
    mock_groups.get_groups_from_integration.side_effect = [
        [{"name": "AWS-Group1", "members": []}],
        [{"DisplayName": "Group1", "GroupMemberships": []}],
    ]
    mock_filters.get_unique_nested_dicts.return_value = []
    mock_identity_store.list_users.return_value = []
    mock_sync_users.return_value = ([], [])

    # Act
    identity_center.synchronize(enable_groups_sync=False)

    # Assert
    mock_sync_users.assert_called_once()
    mock_sync_groups.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
class TestSyncUsers:
    """Tests for sync_users function."""

    def test_should_create_users_when_enabled(self, mock_filters, mock_entities):
        """Test sync_users creates users when enabled."""
        # Arrange
        source_users = [{"primaryEmail": "user1@example.com"}]
        target_users = []
        mock_filters.compare_lists.return_value = (source_users, [])
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.side_effect = [
            [{"UserId": "user-123"}],  # created users
            [],  # deleted users
        ]

        # Act
        created, deleted = identity_center.sync_users(
            source_users, target_users, enable_user_create=True
        )

        # Assert
        assert len(created) == 1
        assert len(deleted) == 0
        assert mock_entities.provision_entities.call_count == 2

    def test_should_skip_create_when_disabled(self, mock_filters, mock_entities):
        """Test sync_users skips creation when disabled."""
        # Arrange
        source_users = [{"primaryEmail": "user1@example.com"}]
        target_users = []
        mock_filters.compare_lists.return_value = (source_users, [])
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.return_value = []

        # Act
        identity_center.sync_users(source_users, target_users, enable_user_create=False)

        # Assert
        # provision_entities should still be called for deletion
        assert mock_entities.provision_entities.call_count >= 1

    def test_should_delete_all_when_delete_target_all(
        self, mock_filters, mock_entities
    ):
        """Test sync_users deletes all users when delete_target_all is True."""
        # Arrange
        source_users = []
        target_users = [{"UserName": "user1@example.com", "UserId": "user-123"}]
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.side_effect = [
            [],  # created users
            [{"UserId": "user-123"}],  # deleted users
        ]

        # Act
        created, deleted = identity_center.sync_users(
            source_users, target_users, delete_target_all=True
        )

        # Assert
        assert len(created) == 0
        assert len(deleted) == 1


@pytest.mark.unit
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
class TestSyncGroups:
    """Tests for sync_groups function."""

    def test_should_sync_group_memberships(self, mock_filters, mock_entities):
        """Test sync_groups syncs group memberships."""
        # Arrange
        source_groups = [
            {
                "DisplayName": "Group1",
                "members": [{"primaryEmail": "user1@example.com"}],
            }
        ]
        target_groups = [
            {"GroupId": "group-123", "DisplayName": "Group1", "GroupMemberships": []}
        ]
        target_users = [{"UserId": "user-123", "UserName": "user1@example.com"}]

        # Setup filters mock
        mock_filters.preformat_items.side_effect = [
            source_groups,  # preformat source groups
            target_groups,  # compare_lists returns these
        ]
        mock_filters.compare_lists.side_effect = [
            (source_groups, target_groups),  # group comparison
            ([{"primaryEmail": "user1@example.com"}], []),  # membership comparison
        ]

        mock_entities.provision_entities.return_value = [{"MembershipId": "mem-1"}]

        # Act
        created, deleted = identity_center.sync_groups(
            source_groups, target_groups, target_users
        )

        # Assert
        assert isinstance(created, list)
        assert isinstance(deleted, list)

    def test_should_skip_membership_create_when_disabled(
        self, mock_filters, mock_entities
    ):
        """Test sync_groups skips membership creation when disabled."""
        # Arrange
        source_groups = [
            {
                "DisplayName": "Group1",
                "members": [{"primaryEmail": "user1@example.com"}],
            }
        ]
        target_groups = [
            {"GroupId": "group-123", "DisplayName": "Group1", "GroupMemberships": []}
        ]
        target_users = [{"UserId": "user-123", "UserName": "user1@example.com"}]

        mock_filters.preformat_items.side_effect = [
            source_groups,
        ]
        mock_filters.compare_lists.side_effect = [
            (source_groups, target_groups),
            ([{"primaryEmail": "user1@example.com"}], []),
        ]
        mock_entities.provision_entities.return_value = []

        # Act
        identity_center.sync_groups(
            source_groups, target_groups, target_users, enable_membership_create=False
        )

        # Assert
        calls = [call for call in mock_entities.provision_entities.call_args_list]
        assert any("execute=False" in str(call) for call in calls)


@pytest.mark.unit
@patch("modules.aws.identity_center.users")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.identity_store")
class TestProvisionAwsUsers:
    """Tests for provision_aws_users function."""

    def test_should_create_users_successfully(
        self, mock_identity_store, mock_entities, mock_filters, mock_users
    ):
        """Test provision_aws_users creates users successfully."""
        # Arrange
        user_emails = ["user1@example.com", "user2@example.com"]
        mock_users.get_users_from_integration.return_value = [
            {
                "primaryEmail": "user1@example.com",
                "name": {"givenName": "User", "familyName": "One"},
            },
            {
                "primaryEmail": "user2@example.com",
                "name": {"givenName": "User", "familyName": "Two"},
            },
        ]
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.return_value = [
            {"UserId": "user-1"},
            {"UserId": "user-2"},
        ]

        # Act
        result = identity_center.provision_aws_users("create", user_emails)

        # Assert
        assert len(result) == 2
        mock_entities.provision_entities.assert_called_once()

    def test_should_delete_users_successfully(
        self, mock_identity_store, mock_entities, mock_filters, mock_users
    ):
        """Test provision_aws_users deletes users successfully."""
        # Arrange
        user_emails = ["user1@example.com"]
        mock_users.get_users_from_integration.return_value = [
            {"UserName": "user1@example.com", "UserId": "user-1"},
        ]
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.return_value = [
            {"UserId": "user-1"},
        ]

        # Act
        result = identity_center.provision_aws_users("delete", user_emails)

        # Assert
        assert len(result) == 1
        mock_entities.provision_entities.assert_called_once()

    def test_should_raise_error_for_invalid_operation(
        self, mock_identity_store, mock_entities, mock_filters, mock_users
    ):
        """Test provision_aws_users raises error for invalid operation."""
        # Act & Assert
        with pytest.raises(ValueError):
            identity_center.provision_aws_users("invalid", ["user@example.com"])

    def test_should_filter_emails_when_creating_users(
        self, mock_identity_store, mock_entities, mock_filters, mock_users
    ):
        """Test provision_aws_users filters users by email when creating."""
        # Arrange
        user_emails = ["user1@example.com"]
        all_users = [
            {"primaryEmail": "user1@example.com"},
            {"primaryEmail": "user2@example.com"},
            {"primaryEmail": "user3@example.com"},
        ]
        mock_users.get_users_from_integration.return_value = all_users
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.return_value = [{"UserId": "user-1"}]

        # Act
        identity_center.provision_aws_users("create", user_emails)

        # Assert
        call_args = mock_entities.provision_entities.call_args
        # The items passed should only contain user1
        items = call_args[0][1]
        assert len(items) == 1
        assert items[0]["primaryEmail"] == "user1@example.com"
