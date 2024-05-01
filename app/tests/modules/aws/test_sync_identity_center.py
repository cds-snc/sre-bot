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
    for user in users_to_create:
        mock_logger.info.assert_any_call(
            f"Creating user {user['name']['givenName']} {user['name']['familyName']}, primary email: {user['primaryEmail']}"
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
def test_delete_aws_users(mock_delete_user, mock_logger, aws_users):
    users_to_delete = aws_users(3, "user")
    mock_delete_user.side_effect = users_to_delete

    result = sync_identity_center.delete_aws_users(users_to_delete)

    assert result == users_to_delete
    for user in users_to_delete:
        mock_logger.info.assert_any_call(
            f"Deleting user {user['UserName']} with id: {user['UserId']}"
        )
        mock_delete_user.assert_has_calls(
            [call(user["UserId"]) for user in users_to_delete]
        )


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
            enable_delete=False,
            delete_target_all=False,
        )
        in mock_compare_lists.call_args_list
    )
    assert call(source_users) in mock_create_aws_users.call_args_list
    assert call([]) in mock_delete_aws_users.call_args_list
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

    result = sync_identity_center.sync_identity_center_users(source_users, target_users)

    assert result == (source_users, target_users)
    assert (
        call(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
            enable_delete=False,
            delete_target_all=False,
        )
        in mock_compare_lists.call_args_list
    )
    assert call(source_users) in mock_create_aws_users.call_args_list
    assert call(target_users) in mock_delete_aws_users.call_args_list
    assert mock_logger.info.call_count == 1
    assert (
        call("Identified 3 Users to Create and 3 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.sync_identity_center.logger")
@patch("modules.aws.sync_identity_center.delete_aws_users")
@patch("modules.aws.sync_identity_center.create_aws_users")
@patch("modules.aws.sync_identity_center.filters.compare_lists")
def test_sync_identity_center_users_delete_target_all(
    mock_compare_lists,
    mock_create_aws_users,
    mock_delete_aws_users,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)
    mock_compare_lists.return_value = [], target_users
    mock_create_aws_users.return_value = source_users
    mock_delete_aws_users.return_value = target_users

    result = sync_identity_center.sync_identity_center_users(
        source_users, target_users, delete_target_all=True
    )

    assert result == (source_users, target_users)
    assert (
        call(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
            enable_delete=False,
            delete_target_all=True,
        )
        in mock_compare_lists.call_args_list
    )
    assert call([]) in mock_create_aws_users.call_args_list
    assert call(target_users) in mock_delete_aws_users.call_args_list
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
    aws_users,
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


# @patch("modules.aws.sync_identity_center.sync_aws_groups_members")
# @patch("modules.aws.sync_identity_center.sync_aws_users")
# @patch("modules.aws.sync_identity_center.get_source_groups_with_users")
# @patch("modules.aws.sync_identity_center.users.get_unique_users_from_groups")
# @patch("modules.aws.sync_identity_center.identity_store.list_users")
# @patch("modules.aws.sync_identity_center.identity_store.list_groups_with_memberships")
# def test_synchronize_with_defaults(
#     mock_identity_store_list_groups_with_memberships,
#     mock_identity_store_list_users,
#     mock_get_unique_users_from_groups,
#     mock_get_source_groups_with_users,
#     mock_sync_aws_users,
#     mock_sync_aws_groups_members,
# ):
#     result = sync_identity_center.synchronize()

#     assert result == (None, None)

#     assert mock_identity_store_list_groups_with_memberships.not_called
#     assert mock_identity_store_list_users.not_called
#     assert mock_get_unique_users_from_groups.not_called
#     assert mock_get_source_groups_with_users.called
#     assert mock_sync_aws_users.not_called
#     assert mock_sync_aws_groups_members.not_called


# @patch("modules.aws.sync_identity_center.sync_aws_groups_members")
# @patch("modules.aws.sync_identity_center.sync_aws_users")
# @patch("modules.aws.sync_identity_center.get_source_groups_with_users")
# @patch("modules.aws.sync_identity_center.users.get_unique_users_from_groups")
# @patch("modules.aws.sync_identity_center.identity_store.list_users")
# @patch("modules.aws.sync_identity_center.identity_store.list_groups_with_memberships")
# def test_synchronize_with_sync_users_true(
#     mock_identity_store_list_groups_with_memberships,
#     mock_identity_store_list_users,
#     mock_get_unique_users_from_groups,
#     mock_get_source_groups_with_users,
#     mock_sync_aws_users,
#     mock_sync_aws_groups_members,
#     google_groups_w_users,
#     google_users,
#     aws_users,
# ):
#     users = google_users(3, "user")
#     google_groups_with_users = google_groups_w_users(3, 3, "group")
#     mock_get_source_groups_with_users.return_value = google_groups_with_users
#     mock_get_unique_users_from_groups.return_value = users
#     mock_identity_store_list_users.return_value = aws_users
#     mock_sync_aws_users.return_value = "users_sync_status"
#     result = sync_identity_center.synchronize(sync_users=True)

#     assert result == ("users_sync_status", None)

#     assert mock_identity_store_list_groups_with_memberships.not_called
#     assert mock_identity_store_list_users.called
#     assert mock_get_unique_users_from_groups.called_with(
#         google_groups_w_users, "members"
#     )
#     assert mock_get_source_groups_with_users.called_with("email:aws-*")
#     assert mock_sync_aws_users.called_with(users, aws_users)
#     assert mock_sync_aws_groups_members.not_called


# @patch("modules.aws.sync_identity_center.sync_aws_groups_members")
# @patch("modules.aws.sync_identity_center.sync_aws_users")
# @patch("modules.aws.sync_identity_center.get_source_groups_with_users")
# @patch("modules.aws.sync_identity_center.users.get_unique_users_from_groups")
# @patch("modules.aws.sync_identity_center.identity_store.list_users")
# @patch("modules.aws.sync_identity_center.identity_store.list_groups_with_memberships")
# def test_synchronize_with_sync_groups_true(
#     mock_identity_store_list_groups_with_memberships,
#     mock_identity_store_list_users,
#     mock_get_unique_users_from_groups,
#     mock_get_source_groups_with_users,
#     mock_sync_aws_users,
#     mock_sync_aws_groups_members,
#     google_users,
#     google_groups_w_users,
#     aws_users,
#     aws_groups,
# ):
#     unique_users = []
#     google_groups_with_users = google_groups_w_users(3, 3, "group")
#     for group in google_groups_with_users:
#         for user in group["members"]:
#             if user not in unique_users:
#                 unique_users.append(user)
#     mock_get_source_groups_with_users.return_value = google_groups_with_users
#     mock_get_unique_users_from_groups.return_value = unique_users
#     mock_identity_store_list_users.return_value = aws_users
#     mock_sync_aws_groups_members.return_value = "groups_sync_status"
#     result = sync_identity_center.synchronize(sync_groups=True)

#     assert result == (None, "groups_sync_status")

#     assert mock_identity_store_list_groups_with_memberships.called
#     assert mock_identity_store_list_users.not_called
#     assert mock_get_unique_users_from_groups.not_called
#     assert mock_get_source_groups_with_users.called_with("email:aws-*")
#     assert mock_sync_aws_users.not_called
#     assert mock_sync_aws_groups_members.called_with(
#         google_groups_with_users, aws_groups
#     )


# @patch("modules.aws.sync_identity_center.google_directory.list_groups")
# @patch("modules.aws.sync_identity_center.filter_tools.filter_by_condition")
# def test_get_source_groups(
#     mock_filter_by_condition,
#     mock_google_directory_list_groups,
#     google_groups,
# ):
#     mock_google_directory_list_groups.return_value = google_groups
#     mock_filter_by_condition.return_value = google_groups

#     result = sync_identity_center.get_source_groups()

#     assert result == google_groups
#     assert mock_google_directory_list_groups.called_with("email:aws-*")
#     assert mock_filter_by_condition.called_with(
#         google_groups, lambda group: "AWS-" in group["name"]
#     )


# @patch("modules.aws.sync_identity_center.filter_tools.filter_by_condition")
# @patch("modules.aws.sync_identity_center.google_directory.list_groups_with_members")
# def test_get_source_groups_with_users(
#     mock_list_groups_with_members,
#     mock_filter_by_condition,
#     google_groups_w_users,
# ):
#     google_groups_with_users = google_groups_w_users()

#     mock_list_groups_with_members.return_value = google_groups_with_users
#     mock_filter_by_condition.return_value = google_groups_with_users
#     result = sync_identity_center.get_source_groups_with_users()

#     assert result == google_groups_with_users

#     assert mock_list_groups_with_members.call_count == 1
#     assert mock_filter_by_condition.call_count == 1


# @patch("modules.aws.sync_identity_center.identity_store.create_user")
# @patch("modules.aws.sync_identity_center.logger")
# def test_create_users_with_users_list(mock_logger, mock_create_user, google_users):
#     users = google_users(3, "user")
#     external_user = google_users(1, "user", "external.com")[0]
#     users.append(external_user)
#     mock_create_user.side_effect = [
#         "user1_id",
#         "user2_id",
#         "user3_id",
#         "user9_external_id",
#     ]
#     response = sync_identity_center.create_aws_users(users)

#     assert response == ["user1_id", "user2_id", "user3_id", "user9_external_id"]

#     assert mock_create_user.call_count == 4
#     assert mock_logger.info.call_count == 4
#     assert mock_logger.info.call_args_list == [
#         call("Creating user Given_name_0 Family_name_0"),
#         call("Creating user Given_name_1 Family_name_1"),
#         call("Creating user Given_name_2 Family_name_2"),
#         call("Creating user Given_name_0 Family_name_0"),
#     ]


# @patch("modules.aws.sync_identity_center.identity_store.create_user")
# def test_create_users_with_empty_users_list(mock_create_user):
#     result = sync_identity_center.create_aws_users([])
#     assert result == []

#     assert mock_create_user.call_count == 0
