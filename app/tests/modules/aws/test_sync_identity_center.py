import json
from unittest.mock import patch, call
from modules.aws import sync_identity_center


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.create_user")
def test_create_aws_users(mock_create_user, mock_logger, google_users):
    users_to_create = google_users(3, "user")
    mock_create_user.side_effect = users_to_create

    result = sync_identity_center.create_aws_users(users_to_create)

    assert result == users_to_create
    assert mock_create_user.call_count == 3
    for user in users_to_create:
        mock_logger.info.assert_any_call(
            f"Attempting to create user: {user['primaryEmail']}"
        )
        mock_create_user.assert_has_calls(
            [
                call(
                    user["primaryEmail"],
                    user["name"]["givenName"],
                    user["name"]["familyName"],
                )
                for user in users_to_create
            ]
        )
        mock_logger.info.assert_any_call(f"Created user: {user['primaryEmail']}")
    assert (
        call("Finished creation of users. Total users created: 3.")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.create_user")
def test_create_aws_users_with_failure(mock_create_user, mock_logger, google_users):
    users_to_create = google_users(3, "user")
    expected_output = []
    for user in users_to_create:
        expected_output.append(user["primaryEmail"])
    mock_create_user.side_effect = [expected_output[0], None, expected_output[2]]
    del expected_output[1]

    result = sync_identity_center.create_aws_users(users_to_create)

    assert result == expected_output
    assert mock_create_user.call_count == 3
    for i in range(len(users_to_create)):
        mock_logger.info.assert_any_call(
            f"Attempting to create user: {users_to_create[i]['primaryEmail']}"
        )
        mock_create_user.assert_any_call(
            users_to_create[i]["primaryEmail"],
            users_to_create[i]["name"]["givenName"],
            users_to_create[i]["name"]["familyName"],
        )
        if i == 1:
            mock_logger.error.assert_any_call(
                f"Failed to create user: {users_to_create[i]['primaryEmail']}"
            )
        else:
            mock_logger.info.assert_any_call(
                f"Created user: {users_to_create[i]['primaryEmail']}"
            )
    assert (
        call("Finished creation of users. Total users created: 2.")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.create_user")
def test_create_aws_users_empty_list(mock_create_user, mock_logger):
    users_to_create = []
    mock_create_user.side_effect = users_to_create

    result = sync_identity_center.create_aws_users(users_to_create)

    assert result == users_to_create
    assert mock_create_user.call_count == 0


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.delete_user")
def test_delete_aws_users_default(mock_delete_user, mock_logger, aws_users):
    users_to_delete = aws_users(3, "user")

    result = sync_identity_center.delete_aws_users(users_to_delete)

    assert result == []
    assert mock_logger.info.call_count == 5
    assert call("Starting deletion of 3 users.") in mock_logger.info.call_args_list
    for user in users_to_delete:
        mock_logger.info.assert_any_call(f"Deleting user (dry-run): {user['UserName']}")
    assert (
        call("Finished deletion of users. Total users deleted: 0.")
        in mock_logger.info.call_args_list
    )
    mock_delete_user.call_count == 0


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.delete_user")
def test_delete_aws_users_enable_delete_true(mock_delete_user, mock_logger, aws_users):
    users_to_delete = aws_users(3, "user")
    mock_delete_user.return_value = True

    result = sync_identity_center.delete_aws_users(users_to_delete, enable_delete=True)

    assert result == users_to_delete
    assert mock_logger.info.call_count == 8
    assert call("Starting deletion of 3 users.") in mock_logger.info.call_args_list
    for user in users_to_delete:
        mock_logger.info.assert_any_call(
            f"Attempting to delete user: {user['UserName']}"
        )
        mock_delete_user.assert_any_call(user["UserId"])
        mock_logger.info.assert_any_call(f"Deleted user: {user['UserName']}")
    assert (
        call("Finished deletion of users. Total users deleted: 3.")
        in mock_logger.info.call_args_list
    )
    mock_delete_user.call_count == 3


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.delete_user")
def test_delete_aws_users_failed_deletion(mock_delete_user, mock_logger, aws_users):
    users_to_delete = aws_users(3, "user")
    expected_output = users_to_delete.copy()
    del expected_output[1]
    mock_delete_user.side_effect = [True, False, True]

    result = sync_identity_center.delete_aws_users(users_to_delete, enable_delete=True)

    assert result == expected_output
    assert mock_logger.info.call_count == 7
    assert call("Starting deletion of 3 users.") in mock_logger.info.call_args_list
    # for user in users_to_delete:
    for i in range(len(users_to_delete)):
        mock_logger.info.assert_any_call(
            f"Attempting to delete user: {users_to_delete[i]['UserName']}"
        )
        mock_delete_user.assert_any_call(users_to_delete[i]["UserId"])
        if i == 1:
            mock_logger.error.assert_any_call(
                f"Failed to delete user: {users_to_delete[i]['UserName']}"
            )
        else:
            mock_logger.info.assert_any_call(
                f"Deleted user: {users_to_delete[i]['UserName']}"
            )
    assert (
        call("Finished deletion of users. Total users deleted: 2.")
        in mock_logger.info.call_args_list
    )
    mock_delete_user.call_count == 3


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.delete_user")
def test_delete_aws_users_empty_list(mock_delete_user, mock_logger):
    users_to_delete = []
    mock_delete_user.side_effect = users_to_delete

    result = sync_identity_center.delete_aws_users(users_to_delete)

    assert result == users_to_delete
    assert mock_delete_user.call_count == 0


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.delete_aws_users")
@patch("modules.aws.sync_identity_center.create_aws_users")
@patch("modules.aws.sync_identity_center.filters.compare_lists")
def test_sync_identity_center_users_default(
    mock_compare_lists,
    mock_create_aws_users,
    mock_delete_aws_users,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)[:3]
    mock_compare_lists.return_value = source_users, []
    mock_create_aws_users.return_value = source_users
    mock_delete_aws_users.return_value = []

    result = sync_identity_center.sync_identity_center_users(source_users, target_users)

    assert result == (source_users, [])

    assert (
        call(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
        )
        in mock_compare_lists.call_args_list
    )
    assert call(source_users) in mock_create_aws_users.call_args_list
    assert call([], enable_delete=False) in mock_delete_aws_users.call_args_list
    assert mock_logger.info.call_count == 1
    assert (
        call("Identified 3 Users to Create and 0 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.delete_aws_users")
@patch("modules.aws.sync_identity_center.create_aws_users")
@patch("modules.aws.sync_identity_center.filters.compare_lists")
def test_sync_identity_center_users_enable_delete_true(
    mock_compare_lists,
    mock_create_aws_users,
    mock_delete_aws_users,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)[:3]
    mock_compare_lists.return_value = source_users, target_users
    mock_create_aws_users.return_value = source_users
    mock_delete_aws_users.return_value = target_users

    result = sync_identity_center.sync_identity_center_users(
        source_users, target_users, enable_delete=True
    )

    assert result == (source_users, target_users)
    assert (
        call(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
        )
        in mock_compare_lists.call_args_list
    )
    assert call(source_users) in mock_create_aws_users.call_args_list
    assert (
        call(target_users, enable_delete=True) in mock_delete_aws_users.call_args_list
    )
    assert mock_logger.info.call_count == 1
    assert (
        call("Identified 3 Users to Create and 3 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.delete_aws_users")
@patch("modules.aws.sync_identity_center.create_aws_users")
@patch("modules.aws.sync_identity_center.filters.compare_lists")
def test_sync_identity_center_users_delete_target_all_dry_run(
    mock_compare_lists,
    mock_create_aws_users,
    mock_delete_aws_users,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)
    mock_create_aws_users.return_value = []
    mock_delete_aws_users.return_value = target_users

    result = sync_identity_center.sync_identity_center_users(
        source_users, target_users, delete_target_all=True
    )

    assert result == ([], target_users)
    assert mock_compare_lists.call_count == 0
    assert call([]) in mock_create_aws_users.call_args_list
    assert (
        call(target_users, enable_delete=False) in mock_delete_aws_users.call_args_list
    )
    assert mock_logger.info.call_count == 1
    assert (
        call("Identified 0 Users to Create and 6 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.delete_aws_users")
@patch("modules.aws.sync_identity_center.create_aws_users")
@patch("modules.aws.sync_identity_center.filters.compare_lists")
def test_sync_identity_center_users_delete_target_all_enable_delete(
    mock_compare_lists,
    mock_create_aws_users,
    mock_delete_aws_users,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)
    mock_create_aws_users.return_value = []
    mock_delete_aws_users.return_value = target_users

    result = sync_identity_center.sync_identity_center_users(
        source_users, target_users, enable_delete=True, delete_target_all=True
    )

    assert result == ([], target_users)
    assert mock_compare_lists.call_count == 0
    assert call([]) in mock_create_aws_users.call_args_list
    assert (
        call(target_users, enable_delete=True) in mock_delete_aws_users.call_args_list
    )
    assert mock_logger.info.call_count == 1
    assert (
        call("Identified 0 Users to Create and 6 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.filters.filter_by_condition")
@patch("modules.aws.sync_identity_center.identity_store.create_group_membership")
def test_create_group_memberships(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups,
    aws_users,
    google_users,
):
    group = aws_groups(1)[0]
    target_users = aws_users(3)
    users_to_add = google_users(3)
    mock_filter_by_condition.side_effect = target_users

    mock_create_group_membership.side_effect = [
        "membership1",
        "membership2",
        "membership3",
    ]

    result = sync_identity_center.create_group_memberships(
        group, users_to_add, target_users
    )

    assert result == ["membership1", "membership2", "membership3"]
    for user in users_to_add:
        print(f"Adding user {user['name']['fullName']} to group {group['DisplayName']}")
        mock_logger.info.assert_any_call(
            f"Added user {user['name']['fullName']} to group {group['DisplayName']}"
        )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[0]["UserId"]
        )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[1]["UserId"]
        )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[2]["UserId"]
        )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.filters.filter_by_condition")
@patch("modules.aws.sync_identity_center.identity_store.create_group_membership")
def test_create_group_memberships_with_empty_target_users(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups,
    google_users,
):
    group = aws_groups(1)[0]
    target_users = []
    users_to_add = google_users(3)
    mock_filter_by_condition.side_effect = target_users

    mock_create_group_membership.side_effect = [
        "membership1",
        "membership2",
        "membership3",
    ]

    result = sync_identity_center.create_group_memberships(
        group, users_to_add, target_users
    )

    assert result == []
    assert mock_create_group_membership.call_count == 0
    assert mock_filter_by_condition.call_count == 0
    assert mock_logger.info.call_count == 0
    assert mock_logger.warn.call_count == 1


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.filters.filter_by_condition")
@patch("modules.aws.sync_identity_center.identity_store.create_group_membership")
def test_create_group_memberships_with_empty_users_to_add(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups,
    aws_users,
):
    group = aws_groups(1)[0]
    target_users = aws_users(3)
    users_to_add = []
    mock_filter_by_condition.side_effect = target_users

    mock_create_group_membership.side_effect = [
        "membership1",
        "membership2",
        "membership3",
    ]

    result = sync_identity_center.create_group_memberships(
        group, users_to_add, target_users
    )

    assert result == []
    assert mock_create_group_membership.call_count == 0
    assert mock_filter_by_condition.call_count == 0
    assert mock_logger.info.call_count == 0


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.filters.filter_by_condition")
@patch("modules.aws.sync_identity_center.identity_store.create_group_membership")
def test_create_group_memberships_matching_user_not_found(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups,
    aws_users,
    google_users,
):
    group = aws_groups(1)[0]
    target_users = aws_users(2)
    users_to_add = google_users(3)
    mock_filter_by_condition.side_effect = [
        target_users[0],
        target_users[1],
        None,
    ]

    mock_create_group_membership.side_effect = [
        "membership1",
        "membership2",
    ]

    result = sync_identity_center.create_group_memberships(
        group, users_to_add, target_users
    )

    assert result == ["membership1", "membership2"]
    for user in users_to_add[:2]:
        print(f"Adding user {user['name']['fullName']} to group {group['DisplayName']}")
        mock_logger.info.assert_any_call(
            f"Added user {user['name']['fullName']} to group {group['DisplayName']}"
        )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[0]["UserId"]
        )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[1]["UserId"]
        )
    mock_logger.info.assert_any_call(
        f"User {users_to_add[2]['primaryEmail']} not found in the target system"
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.delete_group_membership")
def test_delete_group_memberships(
    mock_delete_group_membership,
    mock_logger,
    aws_users,
    aws_groups_w_users,
):
    group = aws_groups_w_users(1, 6)[0]
    users_to_remove = aws_users(3)

    mock_delete_group_membership.side_effect = [
        "membership_id_1",
        "membership_id_2",
        "membership_id_3",
    ]

    result = sync_identity_center.delete_group_memberships(group, users_to_remove)

    assert result == [
        "membership_id_1",
        "membership_id_2",
        "membership_id_3",
    ]
    assert mock_delete_group_membership.call_count == 3
    for user in users_to_remove:
        mock_logger.info.assert_any_call(
            f"Removing user {user['UserName']} from group {group['DisplayName']}"
        )
        mock_logger.info.assert_any_call(
            f"Removed user {user['UserName']} from group {group['DisplayName']}"
        )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.delete_group_membership")
def test_delete_group_memberships_with_missing_users(
    mock_delete_group_membership,
    mock_logger,
    aws_users,
    aws_groups_w_users,
):
    group = aws_groups_w_users(1, 6)[0]
    users_to_remove = aws_users(3)
    missing_users_to_remove = aws_users(3, prefix="missing-")
    users_to_remove.extend(missing_users_to_remove)

    mock_delete_group_membership.side_effect = [
        "membership_id_1",
        "membership_id_2",
        "membership_id_3",
    ]

    result = sync_identity_center.delete_group_memberships(group, users_to_remove)

    assert result == [
        "membership_id_1",
        "membership_id_2",
        "membership_id_3",
    ]
    assert mock_delete_group_membership.call_count == 3

    for user in users_to_remove[:3]:
        mock_logger.info.assert_any_call(
            f"Removing user {user['UserName']} from group {group['DisplayName']}"
        )
        mock_logger.info.assert_any_call(
            f"Removed user {user['UserName']} from group {group['DisplayName']}"
        )
    for missing_user in missing_users_to_remove:
        mock_logger.warn.assert_any_call(
            f"User {missing_user['UserName']} not found in group {group['DisplayName']}"
        )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.identity_store.delete_group_membership")
def test_delete_group_memberships_failed(
    mock_delete_group_membership,
    mock_logger,
    aws_users,
    aws_groups_w_users,
):
    group = aws_groups_w_users(1, 6)[0]
    users_to_remove = aws_users(3)

    mock_delete_group_membership.side_effect = [
        "membership_id_1",
        None,
        "membership_id_3",
    ]

    result = sync_identity_center.delete_group_memberships(group, users_to_remove)

    assert result == [
        "membership_id_1",
        "membership_id_3",
    ]
    assert mock_delete_group_membership.call_count == 3
    for i in range(len(users_to_remove)):
        mock_logger.info.assert_any_call(
            f"Removing user {users_to_remove[i]['UserName']} from group {group['DisplayName']}"
        )
        if i == 1:
            mock_logger.error.assert_any_call(
                f"Failed to remove user {users_to_remove[i]['UserName']} from group {group['DisplayName']}"
            )
        else:
            mock_logger.info.assert_any_call(
                f"Removed user {users_to_remove[i]['UserName']} from group {group['DisplayName']}"
            )
