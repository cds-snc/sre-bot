"""Unit tests for AWS Identity Center synchronization handler."""

from unittest.mock import patch

import pytest

from infrastructure.directory.models import DirectoryUser
from infrastructure.operations import OperationResult, OperationStatus
from modules.aws import identity_center
from modules.provisioning import users


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
                        {"primaryEmail": f"user{i + 1}@example.com"},
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


def _transient_error() -> OperationResult:
    return OperationResult.error(
        OperationStatus.TRANSIENT_ERROR,
        message="Rate exceeded",
        error_code="ThrottlingException",
    )


def _conflict_error() -> OperationResult:
    return OperationResult.error(
        OperationStatus.PERMANENT_ERROR,
        message="Resource already exists",
        error_code="ConflictException",
    )


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.build_identity_center_adapter")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_synchronize_users_and_groups_with_defaults(
    mock_sync_groups,
    mock_sync_users,
    mock_build_adapter,
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
    mock_build_adapter.return_value.list_users.return_value = OperationResult.success(data=[])
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
@patch("modules.aws.identity_center.build_identity_center_adapter")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_skip_user_sync_when_disabled(
    mock_sync_groups,
    mock_sync_users,
    mock_build_adapter,
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
    mock_build_adapter.return_value.list_users.return_value = OperationResult.success(data=[])
    mock_sync_groups.return_value = ([], [])

    # Act
    identity_center.synchronize(enable_users_sync=False)

    # Assert
    mock_sync_users.assert_not_called()
    mock_sync_groups.assert_called_once()


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.build_identity_center_adapter")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_skip_group_sync_when_disabled(
    mock_sync_groups,
    mock_sync_users,
    mock_build_adapter,
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
    mock_build_adapter.return_value.list_users.return_value = OperationResult.success(data=[])
    mock_sync_users.return_value = ([], [])

    # Act
    identity_center.synchronize(enable_groups_sync=False)

    # Assert
    mock_sync_users.assert_called_once()
    mock_sync_groups.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.build_identity_center_adapter")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_pass_the_post_sync_user_listing_to_group_sync(
    mock_sync_groups,
    mock_sync_users,
    mock_build_adapter,
    mock_filters,
    mock_groups,
):
    """Group sync receives the users re-listed after user sync, not the initial listing.

    Stub strategy: list_users returns two distinct successful listings in order;
    the second must reach sync_groups because user sync may have created users.
    """
    # Arrange
    initial_users = [{"UserId": "u-1", "UserName": "user1@example.com"}]
    relisted_users = initial_users + [{"UserId": "u-2", "UserName": "user2@example.com"}]
    mock_groups.get_groups_from_integration.side_effect = [
        [{"name": "AWS-Group1", "members": []}],
        [{"DisplayName": "Group1", "GroupMemberships": []}],
    ]
    mock_filters.get_unique_nested_dicts.return_value = []
    mock_build_adapter.return_value.list_users.side_effect = [
        OperationResult.success(data=initial_users),
        OperationResult.success(data=relisted_users),
    ]
    mock_sync_users.return_value = ([], [])
    mock_sync_groups.return_value = ([], [])

    # Act
    identity_center.synchronize()

    # Assert
    assert mock_sync_users.call_args[0][1] == initial_users
    assert mock_sync_groups.call_args[0][2] == relisted_users


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.build_identity_center_adapter")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_treat_an_empty_successful_user_listing_as_zero_users(
    mock_sync_groups,
    mock_sync_users,
    mock_build_adapter,
    mock_filters,
    mock_groups,
):
    """A successful listing with no data means zero users, not a failure.

    Stub strategy: list_users succeeds with data=None; synchronize must not raise
    and must hand sync_users an empty target list.
    """
    # Arrange
    mock_groups.get_groups_from_integration.side_effect = [
        [{"name": "AWS-Group1", "members": []}],
        [{"DisplayName": "Group1", "GroupMemberships": []}],
    ]
    mock_filters.get_unique_nested_dicts.return_value = []
    mock_build_adapter.return_value.list_users.return_value = OperationResult.success(data=None)
    mock_sync_users.return_value = ([], [])
    mock_sync_groups.return_value = ([], [])

    # Act
    identity_center.synchronize()

    # Assert
    assert mock_sync_users.call_args[0][1] == []


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.build_identity_center_adapter")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_raise_when_target_user_listing_fails_before_sync(
    mock_sync_groups,
    mock_sync_users,
    mock_build_adapter,
    mock_filters,
    mock_groups,
):
    """A failed Identity Center user listing raises the provisioning users error.

    Stub strategy: the adapter's list_users returns a transient error result;
    synchronize must raise DirectoryUsersUnavailableError carrying the result's
    message and error_code, and neither sync step may run on a partial view.
    """
    # Arrange
    mock_groups.get_groups_from_integration.side_effect = [
        [{"name": "AWS-Group1", "members": []}],  # source groups
        [{"DisplayName": "Group1", "GroupMemberships": []}],  # target groups
    ]
    mock_filters.get_unique_nested_dicts.return_value = []
    mock_build_adapter.return_value.list_users.return_value = _transient_error()

    # Act & Assert
    with pytest.raises(users.DirectoryUsersUnavailableError) as excinfo:
        identity_center.synchronize()

    assert excinfo.value.message == "Rate exceeded"
    assert excinfo.value.error_code == "ThrottlingException"
    mock_sync_users.assert_not_called()
    mock_sync_groups.assert_not_called()


@pytest.mark.unit
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.build_identity_center_adapter")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_should_raise_when_user_relisting_after_user_sync_fails(
    mock_sync_groups,
    mock_sync_users,
    mock_build_adapter,
    mock_filters,
    mock_groups,
):
    """A failed re-listing after user sync raises before group sync runs.

    Stub strategy: the first list_users succeeds and the second fails; group sync
    must not run against a stale or missing user list.
    """
    # Arrange
    mock_groups.get_groups_from_integration.side_effect = [
        [{"name": "AWS-Group1", "members": []}],
        [{"DisplayName": "Group1", "GroupMemberships": []}],
    ]
    mock_filters.get_unique_nested_dicts.return_value = []
    mock_build_adapter.return_value.list_users.side_effect = [
        OperationResult.success(data=[]),
        _transient_error(),
    ]
    mock_sync_users.return_value = ([], [])

    # Act & Assert
    with pytest.raises(users.DirectoryUsersUnavailableError) as excinfo:
        identity_center.synchronize()

    assert excinfo.value.error_code == "ThrottlingException"
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
        created, deleted = identity_center.sync_users(source_users, target_users, enable_user_create=True)

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

    def test_should_delete_all_when_delete_target_all(self, mock_filters, mock_entities):
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
        created, deleted = identity_center.sync_users(source_users, target_users, delete_target_all=True)

        # Assert
        assert len(created) == 0
        assert len(deleted) == 1

    def test_should_pass_the_local_user_bridges_to_provision_entities(self, mock_filters, mock_entities):
        """Creation and deletion are provisioned through the module's adapter bridges.

        Stub strategy: provision_entities is mocked, so only the callable handed to
        it is inspected -- by identity, which catches a partially swapped call site.
        """
        # Arrange
        mock_filters.compare_lists.return_value = ([], [])
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.return_value = []

        # Act
        identity_center.sync_users([], [])

        # Assert
        create_call, delete_call = mock_entities.provision_entities.call_args_list
        assert create_call.args[0] is identity_center._create_user
        assert delete_call.args[0] is identity_center._delete_user


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
        target_groups = [{"GroupId": "group-123", "DisplayName": "Group1", "GroupMemberships": []}]
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
        created, deleted = identity_center.sync_groups(source_groups, target_groups, target_users)

        # Assert
        assert isinstance(created, list)
        assert isinstance(deleted, list)

    def test_should_skip_membership_create_when_disabled(self, mock_filters, mock_entities):
        """Test sync_groups skips membership creation when disabled."""
        # Arrange
        source_groups = [
            {
                "DisplayName": "Group1",
                "members": [{"primaryEmail": "user1@example.com"}],
            }
        ]
        target_groups = [{"GroupId": "group-123", "DisplayName": "Group1", "GroupMemberships": []}]
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
        identity_center.sync_groups(source_groups, target_groups, target_users, enable_membership_create=False)

        # Assert
        calls = [call for call in mock_entities.provision_entities.call_args_list]
        assert any("execute=False" in str(call) for call in calls)

    def test_should_pass_the_local_membership_bridges_to_provision_entities(self, mock_filters, mock_entities):
        """Membership creation and deletion are provisioned through the adapter bridges.

        Stub strategy: one matched group drives exactly one create and one delete
        provision_entities call; the callables are compared by identity.
        """
        # Arrange
        source_groups = [{"DisplayName": "Group1", "members": []}]
        target_groups = [{"GroupId": "group-123", "DisplayName": "Group1", "GroupMemberships": []}]
        mock_filters.preformat_items.return_value = source_groups
        mock_filters.compare_lists.side_effect = [
            (source_groups, target_groups),
            ([], []),
        ]
        mock_entities.provision_entities.return_value = []

        # Act
        identity_center.sync_groups(source_groups, target_groups, [])

        # Assert
        create_call, delete_call = mock_entities.provision_entities.call_args_list
        assert create_call.args[0] is identity_center._create_group_membership
        assert delete_call.args[0] is identity_center._delete_group_membership


@pytest.mark.unit
@patch("modules.aws.identity_center.users")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.entities")
class TestProvisionAwsUsers:
    """Tests for provision_aws_users function."""

    def test_should_create_users_successfully(self, mock_entities, mock_filters, mock_users):
        """Test provision_aws_users creates users successfully."""
        # Arrange
        user_emails = ["user1@example.com", "user2@example.com"]
        mock_users.get_users_from_integration.return_value = [
            DirectoryUser(
                email="user1@example.com",
                provider_user_id="id-1",
                given_name="User",
                family_name="One",
            ),
            DirectoryUser(
                email="user2@example.com",
                provider_user_id="id-2",
                given_name="User",
                family_name="Two",
            ),
        ]
        mock_entities.provision_entities.return_value = [
            {"UserId": "user-1"},
            {"UserId": "user-2"},
        ]

        # Act
        result = identity_center.provision_aws_users("create", user_emails)

        # Assert
        assert len(result) == 2
        mock_entities.provision_entities.assert_called_once()
        mock_filters.preformat_items.assert_not_called()

    def test_should_build_the_create_payload_from_directory_user_attributes(self, mock_entities, mock_filters, mock_users):
        """The create payload is built explicitly, not splatted from a Google dict."""
        # Arrange
        mock_users.get_users_from_integration.return_value = [
            DirectoryUser(
                email="user1@example.com",
                provider_user_id="id-1",
                given_name="User",
                family_name="One",
            ),
        ]
        mock_entities.provision_entities.return_value = [{"UserId": "user-1"}]

        # Act
        identity_center.provision_aws_users("create", ["user1@example.com"])

        # Assert
        items = mock_entities.provision_entities.call_args[0][1]
        assert items == [
            {
                "primaryEmail": "user1@example.com",
                "email": "user1@example.com",
                "log_user_name": "user1@example.com",
                "first_name": "User",
                "family_name": "One",
            }
        ]

    def test_should_match_requested_emails_case_insensitively_when_creating_users(self, mock_entities, mock_filters, mock_users):
        """The provider lowercases emails; requested addresses may not be."""
        # Arrange
        mock_users.get_users_from_integration.return_value = [
            DirectoryUser(email="user1@example.com", provider_user_id="id-1"),
        ]
        mock_entities.provision_entities.return_value = [{"UserId": "user-1"}]

        # Act
        identity_center.provision_aws_users("create", ["User1@Example.com"])

        # Assert
        items = mock_entities.provision_entities.call_args[0][1]
        assert [item["email"] for item in items] == ["user1@example.com"]

    def test_should_delete_users_successfully(self, mock_entities, mock_filters, mock_users):
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

    def test_should_raise_error_for_invalid_operation(self, mock_entities, mock_filters, mock_users):
        """Test provision_aws_users raises error for invalid operation."""
        # Act & Assert
        with pytest.raises(ValueError):
            identity_center.provision_aws_users("invalid", ["user@example.com"])

    def test_should_filter_emails_when_creating_users(self, mock_entities, mock_filters, mock_users):
        """Test provision_aws_users filters users by email when creating."""
        # Arrange
        user_emails = ["user1@example.com"]
        all_users = [
            DirectoryUser(email="user1@example.com", provider_user_id="id-1"),
            DirectoryUser(email="user2@example.com", provider_user_id="id-2"),
            DirectoryUser(email="user3@example.com", provider_user_id="id-3"),
        ]
        mock_users.get_users_from_integration.return_value = all_users
        mock_entities.provision_entities.return_value = [{"UserId": "user-1"}]

        # Act
        identity_center.provision_aws_users("create", user_emails)

        # Assert
        call_args = mock_entities.provision_entities.call_args
        # The items passed should only contain user1
        items = call_args[0][1]
        assert len(items) == 1
        assert items[0]["primaryEmail"] == "user1@example.com"

    def test_should_create_users_through_the_local_create_bridge(self, mock_entities, mock_filters, mock_users):
        """Slack-driven user creation uses the same adapter bridge as the sync."""
        # Arrange
        mock_users.get_users_from_integration.return_value = []
        mock_entities.provision_entities.return_value = []

        # Act
        identity_center.provision_aws_users("create", ["user1@example.com"])

        # Assert
        assert mock_entities.provision_entities.call_args.args[0] is identity_center._create_user

    def test_should_delete_users_through_the_local_delete_bridge(self, mock_entities, mock_filters, mock_users):
        """Slack-driven user deletion uses the same adapter bridge as the sync."""
        # Arrange
        mock_users.get_users_from_integration.return_value = []
        mock_filters.preformat_items.side_effect = lambda items, *args, **kwargs: items
        mock_entities.provision_entities.return_value = []

        # Act
        identity_center.provision_aws_users("delete", ["user1@example.com"])

        # Assert
        assert mock_entities.provision_entities.call_args.args[0] is identity_center._delete_user


@pytest.mark.unit
@patch("modules.aws.identity_center.build_identity_center_adapter")
class TestCreateUserBridge:
    """Tests for the create_user bridge between provision_entities and the adapter."""

    def test_should_return_the_new_user_id_on_success(self, mock_build_adapter):
        """A successful create returns the UserId, which provision_entities stores as the response."""
        # Arrange
        mock_build_adapter.return_value.create_user.return_value = OperationResult.success(data="user-123")

        # Act
        response = identity_center._create_user(email="user1@example.com", first_name="User", family_name="One")

        # Assert
        assert response == "user-123"
        mock_build_adapter.return_value.create_user.assert_called_once_with(
            email="user1@example.com", first_name="User", family_name="One"
        )

    def test_should_ignore_surplus_entity_keys(self, mock_build_adapter):
        """The whole entity dict is splatted in; keys the adapter does not take are dropped.

        Stub strategy: the entity mirrors the preformatted Google member dict the sync
        builds; the adapter must receive only its three named arguments.
        """
        # Arrange
        mock_build_adapter.return_value.create_user.return_value = OperationResult.success(data="user-123")
        entity = {
            "primaryEmail": "user1@example.com",
            "name": {"givenName": "User", "familyName": "One"},
            "email": "user1@example.com",
            "log_user_name": "user1@example.com",
            "first_name": "User",
            "family_name": "One",
        }

        # Act
        response = identity_center._create_user(**entity)

        # Assert
        assert response == "user-123"
        mock_build_adapter.return_value.create_user.assert_called_once_with(
            email="user1@example.com", first_name="User", family_name="One"
        )

    def test_should_return_false_on_a_transient_error(self, mock_build_adapter):
        """A failed create is reported as False so provision_entities records a failed entity."""
        # Arrange
        mock_build_adapter.return_value.create_user.return_value = _transient_error()

        # Act
        response = identity_center._create_user(email="user1@example.com", first_name="User", family_name="One")

        # Assert
        assert response is False

    def test_should_return_false_when_the_user_already_exists(self, mock_build_adapter):
        """An "already exists" conflict arrives as PERMANENT_ERROR and is a failed entity, not a crash."""
        # Arrange
        mock_build_adapter.return_value.create_user.return_value = _conflict_error()

        # Act
        response = identity_center._create_user(email="user1@example.com", first_name="User", family_name="One")

        # Assert
        assert response is False

    def test_should_return_false_when_a_successful_result_carries_no_user_id(self, mock_build_adapter):
        """A success without a UserId is falsy, so the entity is recorded as failed."""
        # Arrange
        mock_build_adapter.return_value.create_user.return_value = OperationResult.success(data=None)

        # Act
        response = identity_center._create_user(email="user1@example.com", first_name="User", family_name="One")

        # Assert
        assert response is False

    def test_should_log_status_and_error_code_on_failure(self, mock_build_adapter):
        """Failures are logged with the result's status and error_code for diagnosis."""
        # Arrange
        mock_build_adapter.return_value.create_user.return_value = _conflict_error()

        # Act
        with patch("modules.aws.identity_center.logger") as mock_logger:
            identity_center._create_user(email="user1@example.com", first_name="User", family_name="One")

        # Assert
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["status"] == OperationStatus.PERMANENT_ERROR.value
        assert kwargs["error_code"] == "ConflictException"


@pytest.mark.unit
@patch("modules.aws.identity_center.build_identity_center_adapter")
class TestDeleteUserBridge:
    """Tests for the delete_user bridge between provision_entities and the adapter."""

    def test_should_return_true_on_success(self, mock_build_adapter):
        """A successful delete returns True, matching the legacy response."""
        # Arrange
        mock_build_adapter.return_value.delete_user.return_value = OperationResult.success(data=True)

        # Act
        response = identity_center._delete_user(user_id="user-123")

        # Assert
        assert response is True
        mock_build_adapter.return_value.delete_user.assert_called_once_with(user_id="user-123")

    def test_should_ignore_surplus_entity_keys(self, mock_build_adapter):
        """The raw Identity Store user dict plus preformatted keys is splatted in; only user_id is used."""
        # Arrange
        mock_build_adapter.return_value.delete_user.return_value = OperationResult.success(data=True)
        entity = {
            "UserId": "user-123",
            "UserName": "user1@example.com",
            "Emails": [{"Value": "user1@example.com"}],
            "Name": {"GivenName": "User", "FamilyName": "One"},
            "user_id": "user-123",
            "log_user_name": "user1@example.com",
        }

        # Act
        response = identity_center._delete_user(**entity)

        # Assert
        assert response is True
        mock_build_adapter.return_value.delete_user.assert_called_once_with(user_id="user-123")

    def test_should_return_false_on_error(self, mock_build_adapter):
        """A failed delete is reported as False so provision_entities records a failed entity."""
        # Arrange
        mock_build_adapter.return_value.delete_user.return_value = _transient_error()

        # Act
        response = identity_center._delete_user(user_id="user-123")

        # Assert
        assert response is False

    def test_should_log_status_and_error_code_on_failure(self, mock_build_adapter):
        """Failures are logged with the result's status and error_code for diagnosis."""
        # Arrange
        mock_build_adapter.return_value.delete_user.return_value = _transient_error()

        # Act
        with patch("modules.aws.identity_center.logger") as mock_logger:
            identity_center._delete_user(user_id="user-123")

        # Assert
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["status"] == OperationStatus.TRANSIENT_ERROR.value
        assert kwargs["error_code"] == "ThrottlingException"


@pytest.mark.unit
@patch("modules.aws.identity_center.build_identity_center_adapter")
class TestCreateGroupMembershipBridge:
    """Tests for the create_group_membership bridge between provision_entities and the adapter."""

    def test_should_return_the_membership_id_on_success(self, mock_build_adapter):
        """A successful create returns the MembershipId, which provision_entities stores as the response."""
        # Arrange
        mock_build_adapter.return_value.create_group_membership.return_value = OperationResult.success(data="mem-1")

        # Act
        response = identity_center._create_group_membership(group_id="group-123", user_id="user-123")

        # Assert
        assert response == "mem-1"
        mock_build_adapter.return_value.create_group_membership.assert_called_once_with(group_id="group-123", user_id="user-123")

    def test_should_ignore_surplus_entity_keys(self, mock_build_adapter):
        """The Google member dict plus sync-added keys is splatted in; only group_id and user_id are used."""
        # Arrange
        mock_build_adapter.return_value.create_group_membership.return_value = OperationResult.success(data="mem-1")
        entity = {
            "primaryEmail": "user1@example.com",
            "user_id": "user-123",
            "group_id": "group-123",
            "log_user_name": "user1@example.com",
            "log_group_name": "Group1",
        }

        # Act
        response = identity_center._create_group_membership(**entity)

        # Assert
        assert response == "mem-1"
        mock_build_adapter.return_value.create_group_membership.assert_called_once_with(group_id="group-123", user_id="user-123")

    def test_should_return_false_on_a_transient_error(self, mock_build_adapter):
        """A failed create is reported as False so provision_entities records a failed entity."""
        # Arrange
        mock_build_adapter.return_value.create_group_membership.return_value = _transient_error()

        # Act
        response = identity_center._create_group_membership(group_id="group-123", user_id="user-123")

        # Assert
        assert response is False

    def test_should_return_false_when_the_membership_already_exists(self, mock_build_adapter):
        """An "already exists" conflict arrives as PERMANENT_ERROR and is a failed entity, not a crash."""
        # Arrange
        mock_build_adapter.return_value.create_group_membership.return_value = _conflict_error()

        # Act
        response = identity_center._create_group_membership(group_id="group-123", user_id="user-123")

        # Assert
        assert response is False

    def test_should_log_status_and_error_code_on_failure(self, mock_build_adapter):
        """Failures are logged with the result's status and error_code for diagnosis."""
        # Arrange
        mock_build_adapter.return_value.create_group_membership.return_value = _conflict_error()

        # Act
        with patch("modules.aws.identity_center.logger") as mock_logger:
            identity_center._create_group_membership(group_id="group-123", user_id="user-123")

        # Assert
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["status"] == OperationStatus.PERMANENT_ERROR.value
        assert kwargs["error_code"] == "ConflictException"


@pytest.mark.unit
@patch("modules.aws.identity_center.build_identity_center_adapter")
class TestDeleteGroupMembershipBridge:
    """Tests for the delete_group_membership bridge between provision_entities and the adapter."""

    def test_should_return_true_on_success(self, mock_build_adapter):
        """A successful delete returns True, matching the legacy response."""
        # Arrange
        mock_build_adapter.return_value.delete_group_membership.return_value = OperationResult.success(data=True)

        # Act
        response = identity_center._delete_group_membership(membership_id="mem-1")

        # Assert
        assert response is True
        mock_build_adapter.return_value.delete_group_membership.assert_called_once_with(membership_id="mem-1")

    def test_should_ignore_surplus_entity_keys(self, mock_build_adapter):
        """The target membership dict plus sync-added keys is splatted in; only membership_id is used."""
        # Arrange
        mock_build_adapter.return_value.delete_group_membership.return_value = OperationResult.success(data=True)
        entity = {
            "MembershipId": "mem-1",
            "MemberId": {"UserId": "user-123", "UserName": "user1@example.com"},
            "membership_id": "mem-1",
            "log_user_name": "user1@example.com",
            "log_group_name": "Group1",
        }

        # Act
        response = identity_center._delete_group_membership(**entity)

        # Assert
        assert response is True
        mock_build_adapter.return_value.delete_group_membership.assert_called_once_with(membership_id="mem-1")

    def test_should_return_false_on_error(self, mock_build_adapter):
        """A failed delete is reported as False so provision_entities records a failed entity."""
        # Arrange
        mock_build_adapter.return_value.delete_group_membership.return_value = _transient_error()

        # Act
        response = identity_center._delete_group_membership(membership_id="mem-1")

        # Assert
        assert response is False

    def test_should_log_status_and_error_code_on_failure(self, mock_build_adapter):
        """Failures are logged with the result's status and error_code for diagnosis."""
        # Arrange
        mock_build_adapter.return_value.delete_group_membership.return_value = _transient_error()

        # Act
        with patch("modules.aws.identity_center.logger") as mock_logger:
            identity_center._delete_group_membership(membership_id="mem-1")

        # Assert
        kwargs = mock_logger.error.call_args.kwargs
        assert kwargs["status"] == OperationStatus.TRANSIENT_ERROR.value
        assert kwargs["error_code"] == "ThrottlingException"
