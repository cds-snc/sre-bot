from unittest.mock import patch, call, ANY, MagicMock
import pytest

from modules.aws import identity_center


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.provisioning.entities.logger")
@patch("modules.aws.identity_center.identity_store.create_user")
@patch("modules.aws.identity_center.identity_store.delete_user")
@patch("modules.aws.identity_center.identity_store.create_group_membership")
@patch("modules.aws.identity_center.identity_store.delete_group_membership")
@patch("modules.aws.identity_center.identity_store.list_users")
@patch("modules.aws.identity_center.groups.get_groups_with_members_from_integration")
def test_synchronize_enable_all(
    mock_get_groups_with_members_from_integration,
    mock_list_users,
    mock_delete_group_membership,
    mock_create_group_membership,
    mock_delete_user,
    mock_create_user,
    mock_provision_entities_logger,
    mock_logger,
    google_groups_w_users,
    google_users,
    aws_groups_w_users,
    aws_users,
):
    # 3 groups, with 9 users in each group
    source_groups = google_groups_w_users(3, 9, group_prefix="AWS-")
    # only keep first 6 users in groups
    for group in source_groups:
        group["members"] = group["members"][:6]

    # 3 groups, with 9 users in each group
    target_groups = aws_groups_w_users(3, 9)
    # only keep last 6 users in groups
    for group in target_groups:
        group["GroupMemberships"] = group["GroupMemberships"][3:]

    # Setup source and target groups for expected output
    mock_get_groups_with_members_from_integration.side_effect = [
        source_groups,
        target_groups,
    ]

    create_groupmembership_side_effect = [
        "aws-group_id1-user-email1@test.com",
        "aws-group_id1-user-email2@test.com",
        "aws-group_id1-user-email3@test.com",
        "aws-group_id2-user-email1@test.com",
        "aws-group_id2-user-email2@test.com",
        "aws-group_id2-user-email3@test.com",
        "aws-group_id3-user-email1@test.com",
        "aws-group_id3-user-email2@test.com",
        "aws-group_id3-user-email3@test.com",
    ]
    delete_group_membership_side_effect = [
        "membership_id_7",
        "membership_id_8",
        "membership_id_9",
        "membership_id_7",
        "membership_id_8",
        "membership_id_9",
        "membership_id_7",
        "membership_id_8",
        "membership_id_9",
    ]

    expected_group_memberships_to_create = [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]

    expected_group_memberships_to_delete = [
        "user-email7@test.com",
        "user-email8@test.com",
        "user-email9@test.com",
        "user-email7@test.com",
        "user-email8@test.com",
        "user-email9@test.com",
        "user-email7@test.com",
        "user-email8@test.com",
        "user-email9@test.com",
    ]

    mock_create_group_membership.side_effect = create_groupmembership_side_effect
    mock_delete_group_membership.side_effect = delete_group_membership_side_effect

    # Setup source and target users for test
    source_users = google_users(9)[:6]
    target_users = aws_users(9)
    # keep last 6 users for the first return value
    # keep first 6 users for the second return value
    mock_list_users.side_effect = [target_users[3:], target_users[:6]]

    # Setup source and target users for expected output
    def create_user_side_effect(email, first_name, family_name, **kwargs):
        return email

    def delete_user_side_effect(user_id, **kwargs):
        return kwargs["UserName"]

    mock_create_user.side_effect = create_user_side_effect
    mock_delete_user.side_effect = delete_user_side_effect

    expected_target_users_created = []
    for user in source_users[:3]:
        expected_target_users_created.append(
            {"entity": user, "response": user["primaryEmail"]}
        )
        user["email"] = user["primaryEmail"]
        user["first_name"] = user["name"]["givenName"]
        user["family_name"] = user["name"]["familyName"]

    deleted_target_users = target_users[6:]
    expected_target_users_deleted = []
    for user in deleted_target_users:
        expected_target_users_deleted.append(
            {"entity": user, "response": user["UserName"]}
        )

    result = identity_center.synchronize(
        enable_users_sync=True,
        enable_groups_sync=True,
        enable_user_delete=True,
        enable_membership_delete=True,
    )

    assert result == {
        "users": (expected_target_users_created, expected_target_users_deleted),
        "groups": (
            expected_group_memberships_to_create,
            expected_group_memberships_to_delete,
        ),
    }

    assert mock_logger.info.call_count == 58
    assert (
        call("synchronize:Found 3 Source Groups and 6 Users")
        in mock_logger.info.call_args_list
    )
    assert (
        call("synchronize:Found 3 Target Groups and 6 Users")
        in mock_logger.info.call_args_list
    )

    assert (
        call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
        in mock_logger.info.call_args_list
    )

    assert (
        call("aws:Starting creation of 3 user(s)")
    ) in mock_provision_entities_logger.info.call_args_list

    for user in expected_target_users_created:
        assert (
            call(f"aws:Successful creation of user(s) {user['entity']['primaryEmail']}")
            in mock_provision_entities_logger.info.call_args_list
        )
    for user in expected_target_users_deleted:
        assert (
            call(f"aws:Successful deletion of user(s) {user['entity']['UserName']}")
            in mock_provision_entities_logger.info.call_args_list
        )
    for group in target_groups:
        for user in expected_group_memberships_to_create:
            assert (
                call(
                    f"create_group_memberships:Successfully added user {user} to group {group['DisplayName']}"
                )
                in mock_logger.info.call_args_list
            )

    for group in target_groups:
        for user in expected_group_memberships_to_delete:
            assert (
                call(
                    f"delete_group_memberships:Successfully removed user {user} from group {group['DisplayName']}"
                )
                in mock_logger.info.call_args_list
            )

    assert mock_create_user.call_count == 3
    assert mock_delete_user.call_count == 3
    assert mock_create_group_membership.call_count == 9
    assert mock_delete_group_membership.call_count == 9


# @patch("modules.aws.identity_center.DRY_RUN", True)
# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.identity_store.create_user")
# @patch("modules.aws.identity_center.identity_store.delete_user")
# @patch("modules.aws.identity_center.identity_store.create_group_membership")
# @patch("modules.aws.identity_center.identity_store.delete_group_membership")
# @patch("modules.aws.identity_center.identity_store.list_users")
# @patch("modules.aws.identity_center.groups.get_groups_with_members_from_integration")
# def test_synchronize_defaults_dry_run_true(
#     mock_get_groups_with_members_from_integration,
#     mock_list_users,
#     mock_delete_group_membership,
#     mock_create_group_membership,
#     mock_delete_user,
#     mock_create_user,
#     mock_logger,
#     google_groups_w_users,
#     aws_groups_w_users,
#     aws_users,
# ):
#     # 3 groups, with 9 users in each group
#     source_groups = google_groups_w_users(3, 9, group_prefix="AWS-")
#     # only keep first 6 users in groups
#     for group in source_groups:
#         group["members"] = group["members"][:6]
#         for member in group["members"]:
#             member["primaryEmail"] = member["primaryEmail"].replace("AWS-", "")

#     # 3 groups, with 9 users in each group
#     target_groups = aws_groups_w_users(3, 9)
#     # only keep last 6 users in groups
#     for group in target_groups:
#         group["GroupMemberships"] = group["GroupMemberships"][3:]

#     mock_get_groups_with_members_from_integration.side_effect = [
#         source_groups,
#         target_groups,
#     ]

#     # keep last 6 users
#     target_users = aws_users(9)
#     mock_list_users.side_effect = [target_users[3:], target_users]

#     expected_target_users_to_create = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]
#     expected_target_users_to_delete = [
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#     ]

#     expected_group_memberships_to_create = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]

#     expected_group_memberships_to_delete = [
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#     ]

#     result = identity_center.synchronize(
#         enable_users_sync=True, enable_groups_sync=True
#     )

#     assert mock_logger.info.call_count == 68
#     assert (
#         call("synchronize:Found 3 Source Groups and 6 Users")
#         in mock_logger.info.call_args_list
#     )
#     assert (
#         call("synchronize:Found 3 Target Groups and 6 Users")
#         in mock_logger.info.call_args_list
#     )

#     assert (
#         call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
#         in mock_logger.info.call_args_list
#     )

#     assert result == {
#         "users": (expected_target_users_to_create, expected_target_users_to_delete),
#         "groups": (
#             expected_group_memberships_to_create,
#             expected_group_memberships_to_delete,
#         ),
#     }

#     assert mock_create_user.call_count == 0
#     assert mock_delete_user.call_count == 0
#     assert mock_create_group_membership.call_count == 0
#     assert mock_delete_group_membership.call_count == 0


# @patch("modules.aws.identity_center.DRY_RUN", False)
# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.identity_store.create_user")
# @patch("modules.aws.identity_center.identity_store.delete_user")
# @patch("modules.aws.identity_center.identity_store.create_group_membership")
# @patch("modules.aws.identity_center.identity_store.delete_group_membership")
# @patch("modules.aws.identity_center.identity_store.list_users")
# @patch("modules.aws.identity_center.groups.get_groups_with_members_from_integration")
# def test_synchronize_enable_delete_dry_run_false(
#     mock_get_groups_with_members_from_integration,
#     mock_list_users,
#     mock_delete_group_membership,
#     mock_create_group_membership,
#     mock_delete_user,
#     mock_create_user,
#     mock_logger,
#     google_groups_w_users,
#     aws_groups_w_users,
#     aws_users,
# ):
#     # 3 groups, with 9 users in each group
#     source_groups = google_groups_w_users(3, 9, group_prefix="AWS-")
#     # only keep first 6 users in groups
#     for group in source_groups:
#         group["members"] = group["members"][:6]
#         for member in group["members"]:
#             member["primaryEmail"] = member["primaryEmail"].replace("AWS-", "")

#     # 3 groups, with 9 users in each group
#     target_groups = aws_groups_w_users(3, 9)
#     # only keep last 6 users in groups
#     for group in target_groups:
#         group["GroupMemberships"] = group["GroupMemberships"][3:]

#     mock_get_groups_with_members_from_integration.side_effect = [
#         source_groups,
#         target_groups,
#     ]

#     # keep last 6 users
#     target_users = aws_users(9)
#     mock_list_users.side_effect = [target_users[3:], target_users]
#     mock_create_user.side_effect = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]
#     mock_create_group_membership.side_effect = [
#         "aws-group_id1-user-email1@test.com",
#         "aws-group_id1-user-email2@test.com",
#         "aws-group_id1-user-email3@test.com",
#         "aws-group_id2-user-email1@test.com",
#         "aws-group_id2-user-email2@test.com",
#         "aws-group_id2-user-email3@test.com",
#         "aws-group_id3-user-email1@test.com",
#         "aws-group_id3-user-email2@test.com",
#         "aws-group_id3-user-email3@test.com",
#     ]
#     mock_delete_group_membership.side_effect = [
#         "membership_id_7",
#         "membership_id_8",
#         "membership_id_9",
#         "membership_id_7",
#         "membership_id_8",
#         "membership_id_9",
#         "membership_id_7",
#         "membership_id_8",
#         "membership_id_9",
#     ]
#     expected_target_users_to_create = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]
#     expected_target_users_to_delete = [
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#     ]

#     expected_group_memberships_to_create = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]

#     expected_group_memberships_to_delete = [
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#     ]

#     result = identity_center.synchronize(
#         enable_users_sync=True,
#         enable_groups_sync=True,
#         enable_user_delete=True,
#         enable_membership_delete=True,
#     )

#     assert result == {
#         "users": (expected_target_users_to_create, expected_target_users_to_delete),
#         "groups": (
#             expected_group_memberships_to_create,
#             expected_group_memberships_to_delete,
#         ),
#     }

#     assert mock_logger.info.call_count == 68
#     assert (
#         call("synchronize:Found 3 Source Groups and 6 Users")
#         in mock_logger.info.call_args_list
#     )
#     assert (
#         call("synchronize:Found 3 Target Groups and 6 Users")
#         in mock_logger.info.call_args_list
#     )

#     assert (
#         call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
#         in mock_logger.info.call_args_list
#     )

#     for user in expected_target_users_to_create:
#         assert (
#             call(f"create_aws_users:Successfully created user {user}")
#             in mock_logger.info.call_args_list
#         )
#     for user in expected_target_users_to_delete:
#         assert (
#             call(f"delete_aws_users:Successfully deleted user {user}")
#             in mock_logger.info.call_args_list
#         )
#     for group in target_groups:
#         for user in expected_target_users_to_create:
#             assert (
#                 call(
#                     f"create_group_memberships:Successfully added user {user} to group {group['DisplayName']}"
#                 )
#                 in mock_logger.info.call_args_list
#             )

#     for group in target_groups:
#         for user in expected_target_users_to_delete:
#             assert (
#                 call(
#                     f"delete_group_memberships:Successfully removed user {user} from group {group['DisplayName']}"
#                 )
#                 in mock_logger.info.call_args_list
#             )

#     assert mock_create_user.call_count == 3
#     assert mock_delete_user.call_count == 3
#     assert mock_create_group_membership.call_count == 9
#     assert mock_delete_group_membership.call_count == 9


# @patch("modules.aws.identity_center.DRY_RUN", True)
# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.identity_store.create_user")
# @patch("modules.aws.identity_center.identity_store.delete_user")
# @patch("modules.aws.identity_center.identity_store.create_group_membership")
# @patch("modules.aws.identity_center.identity_store.delete_group_membership")
# @patch("modules.aws.identity_center.identity_store.list_users")
# @patch("modules.aws.identity_center.groups.get_groups_with_members_from_integration")
# def test_synchronize_enable_delete_dry_run_true(
#     mock_get_groups_with_members_from_integration,
#     mock_list_users,
#     mock_delete_group_membership,
#     mock_create_group_membership,
#     mock_delete_user,
#     mock_create_user,
#     mock_logger,
#     google_groups_w_users,
#     aws_groups_w_users,
#     aws_users,
# ):
#     # 3 groups, with 9 users in each group
#     source_groups = google_groups_w_users(3, 9, group_prefix="AWS-")
#     # only keep first 6 users in groups
#     for group in source_groups:
#         group["members"] = group["members"][:6]
#         for member in group["members"]:
#             member["primaryEmail"] = member["primaryEmail"].replace("AWS-", "")

#     # 3 groups, with 9 users in each group
#     target_groups = aws_groups_w_users(3, 9)
#     # only keep last 6 users in groups
#     for group in target_groups:
#         group["GroupMemberships"] = group["GroupMemberships"][3:]

#     mock_get_groups_with_members_from_integration.side_effect = [
#         source_groups,
#         target_groups,
#     ]

#     # keep last 6 users
#     target_users = aws_users(9)
#     mock_list_users.side_effect = [target_users[3:], target_users]
#     mock_create_user.side_effect = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]
#     mock_create_group_membership.side_effect = [
#         "aws-group_id1-user-email1@test.com",
#         "aws-group_id1-user-email2@test.com",
#         "aws-group_id1-user-email3@test.com",
#         "aws-group_id2-user-email1@test.com",
#         "aws-group_id2-user-email2@test.com",
#         "aws-group_id2-user-email3@test.com",
#         "aws-group_id3-user-email1@test.com",
#         "aws-group_id3-user-email2@test.com",
#         "aws-group_id3-user-email3@test.com",
#     ]
#     mock_delete_group_membership.side_effect = [
#         "membership_id_7",
#         "membership_id_8",
#         "membership_id_9",
#         "membership_id_7",
#         "membership_id_8",
#         "membership_id_9",
#         "membership_id_7",
#         "membership_id_8",
#         "membership_id_9",
#     ]
#     expected_target_users_to_create = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]
#     expected_target_users_to_delete = [
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#     ]

#     expected_group_memberships_to_create = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]

#     expected_group_memberships_to_delete = [
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#         "user-email7@test.com",
#         "user-email8@test.com",
#         "user-email9@test.com",
#     ]

#     result = identity_center.synchronize(
#         enable_users_sync=True,
#         enable_groups_sync=True,
#         enable_user_delete=True,
#         enable_membership_delete=True,
#     )

#     assert result == {
#         "users": (expected_target_users_to_create, expected_target_users_to_delete),
#         "groups": (
#             expected_group_memberships_to_create,
#             expected_group_memberships_to_delete,
#         ),
#     }

#     assert mock_logger.info.call_count == 68
#     assert (
#         call("synchronize:Found 3 Source Groups and 6 Users")
#         in mock_logger.info.call_args_list
#     )
#     assert (
#         call("synchronize:Found 3 Target Groups and 6 Users")
#         in mock_logger.info.call_args_list
#     )

#     assert (
#         call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
#         in mock_logger.info.call_args_list
#     )

#     for user in expected_target_users_to_create:
#         assert (
#             call(f"create_aws_users:DRY_RUN:Successfully created user {user}")
#             in mock_logger.info.call_args_list
#         )
#     for user in expected_target_users_to_delete:
#         assert (
#             call(f"delete_aws_users:DRY_RUN:Successfully deleted user {user}")
#             in mock_logger.info.call_args_list
#         )
#     for group in target_groups:
#         for user in expected_target_users_to_create:
#             assert (
#                 call(
#                     f"create_group_memberships:DRY_RUN:Successfully added user {user} to group {group['DisplayName']}"
#                 )
#                 in mock_logger.info.call_args_list
#             )

#     for group in target_groups:
#         for user in expected_target_users_to_delete:
#             assert (
#                 call(
#                     f"delete_group_memberships:DRY_RUN:Successfully removed user {user} from group {group['DisplayName']}"
#                 )
#                 in mock_logger.info.call_args_list
#             )

#     assert mock_create_user.call_count == 0
#     assert mock_delete_user.call_count == 0
#     assert mock_create_group_membership.call_count == 0
#     assert mock_delete_group_membership.call_count == 0


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.preformat_items")
@patch("modules.aws.identity_center.sync_groups")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.identity_store.list_users")
@patch("modules.aws.identity_center.filters.get_unique_nested_dicts")
@patch("modules.aws.identity_center.groups.get_groups_with_members_from_integration")
def test_synchronize_sync_skip_users_if_false(
    mock_get_groups_with_members_from_integration,
    mock_get_unique_nested_dicts,
    mock_list_users,
    mock_sync_identity_center_users,
    mock_sync_identity_center_groups,
    mock_preformat_items,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
    google_users,
):
    source_groups = google_groups_w_users(3, 6)
    source_users = google_users(6)
    target_groups = aws_groups_w_users(3, 6)
    target_users = aws_users(6)
    mock_get_groups_with_members_from_integration.side_effect = [
        source_groups,
        target_groups,
    ]
    mock_preformat_items.return_value = source_groups
    mock_get_unique_nested_dicts.return_value = source_users
    mock_list_users.return_value = target_users
    mock_sync_identity_center_users.return_value = ("users_created", "users_deleted")
    mock_sync_identity_center_groups.return_value = (
        "memberships_created",
        "memberships_deleted",
    )

    response = identity_center.synchronize(enable_users_sync=False)

    assert response == {
        "users": None,
        "groups": ("memberships_created", "memberships_deleted"),
    }

    assert mock_get_groups_with_members_from_integration.call_count == 2

    google_groups_call = call("google_groups", query="email:aws-*", filters=ANY)
    aws_identity_center_call = call("aws_identity_center")
    assert mock_get_groups_with_members_from_integration.call_args_list == [
        google_groups_call,
        aws_identity_center_call,
    ]

    assert mock_get_unique_nested_dicts.call_count == 1
    assert mock_list_users.call_count == 1
    assert mock_sync_identity_center_users.call_count == 0
    assert mock_sync_identity_center_groups.call_count == 1

    assert (
        call(source_groups, target_groups, target_users, True, False)
        in mock_sync_identity_center_groups.call_args_list
    )

    assert mock_logger.info.call_count == 22
    logger_calls = [call("synchronize:Found 3 Source Groups and 6 Users")]
    for group in source_groups:
        logger_calls.append(
            call(
                f"synchronize:Source:Group {group['name']} has {len(group['members'])} members"
            )
        )
    for user in source_users:
        logger_calls.append(call(f"synchronize:Source:User {user['primaryEmail']}"))
    logger_calls.append(call("synchronize:Found 3 Target Groups and 6 Users"))
    for group in target_groups:
        logger_calls.append(
            call(
                f"synchronize:Target:Group {group['DisplayName']} has {len(group['GroupMemberships'])} members"
            )
        )
    for user in target_users:
        logger_calls.append(call(f"synchronize:Target:User {user['UserName']}"))
    logger_calls.append(call("synchronize:groups:Syncing Groups"))
    logger_calls.append(call("synchronize:groups:Formatting Source Groups"))

    assert mock_logger.info.call_args_list == logger_calls


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.preformat_items")
@patch("modules.aws.identity_center.sync_groups")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.identity_store.list_users")
@patch("modules.aws.identity_center.filters.get_unique_nested_dicts")
@patch("modules.aws.identity_center.groups.get_groups_with_members_from_integration")
def test_synchronize_sync_skip_groups_false_if_false(
    mock_get_groups_with_members_from_integration,
    mock_get_unique_nested_dicts,
    mock_list_users,
    mock_sync_identity_center_users,
    mock_sync_identity_center_groups,
    mock_preformat_items,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
    google_users,
):
    source_groups = google_groups_w_users(3, 6)
    source_users = google_users(6)
    target_groups = aws_groups_w_users(3, 6)
    target_users = aws_users(6)
    mock_get_groups_with_members_from_integration.side_effect = [
        source_groups,
        target_groups,
    ]
    mock_preformat_items.return_value = source_groups
    mock_get_unique_nested_dicts.return_value = source_users
    mock_list_users.return_value = target_users
    mock_sync_identity_center_users.return_value = ("users_created", "users_deleted")
    mock_sync_identity_center_groups.return_value = (
        "memberships_created",
        "memberships_deleted",
    )

    response = identity_center.synchronize(enable_groups_sync=False)

    assert response == {"users": ("users_created", "users_deleted"), "groups": None}

    assert mock_get_groups_with_members_from_integration.call_count == 2

    google_groups_call = call("google_groups", query="email:aws-*", filters=ANY)
    aws_identity_center_call = call("aws_identity_center")
    assert mock_get_groups_with_members_from_integration.call_args_list == [
        google_groups_call,
        aws_identity_center_call,
    ]

    assert mock_get_unique_nested_dicts.call_count == 1
    assert mock_list_users.call_count == 2
    assert mock_sync_identity_center_users.call_count == 1
    assert mock_sync_identity_center_groups.call_count == 0

    assert (
        call(source_users, target_users, True, False)
        in mock_sync_identity_center_users.call_args_list
    )

    assert mock_logger.info.call_count == 21
    logger_calls = [call("synchronize:Found 3 Source Groups and 6 Users")]
    for group in source_groups:
        logger_calls.append(
            call(
                f"synchronize:Source:Group {group['name']} has {len(group['members'])} members"
            )
        )
    for user in source_users:
        logger_calls.append(call(f"synchronize:Source:User {user['primaryEmail']}"))
    logger_calls.append(call("synchronize:Found 3 Target Groups and 6 Users"))
    for group in target_groups:
        logger_calls.append(
            call(
                f"synchronize:Target:Group {group['DisplayName']} has {len(group['GroupMemberships'])} members"
            )
        )
    for user in target_users:
        logger_calls.append(call(f"synchronize:Target:User {user['UserName']}"))
    logger_calls.append(call("synchronize:users:Syncing Users"))

    assert mock_logger.info.call_args_list == logger_calls


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.sync_groups")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.identity_store.list_users")
@patch("modules.aws.identity_center.filters.get_unique_nested_dicts")
@patch("modules.aws.identity_center.groups.get_groups_with_members_from_integration")
def test_synchronize_sync_skip_users_and_groups_if_false(
    mock_get_groups_with_members_from_integration,
    mock_get_unique_nested_dicts,
    mock_list_users,
    mock_sync_identity_center_users,
    mock_sync_identity_center_groups,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
    google_users,
):
    source_groups = google_groups_w_users(3, 6)
    source_users = google_users(6)
    target_groups = aws_groups_w_users(3, 6)
    target_users = aws_users(6)
    mock_get_groups_with_members_from_integration.side_effect = [
        source_groups,
        target_groups,
    ]
    mock_get_unique_nested_dicts.return_value = source_users
    mock_list_users.return_value = target_users
    mock_sync_identity_center_users.return_value = ("users_created", "users_deleted")
    mock_sync_identity_center_groups.return_value = (
        "memberships_created",
        "memberships_deleted",
    )

    response = identity_center.synchronize(
        enable_groups_sync=False, enable_users_sync=False
    )

    assert response == {"users": None, "groups": None}

    assert mock_get_groups_with_members_from_integration.call_count == 2

    google_groups_call = call("google_groups", query="email:aws-*", filters=ANY)
    aws_identity_center_call = call("aws_identity_center")
    assert mock_get_groups_with_members_from_integration.call_args_list == [
        google_groups_call,
        aws_identity_center_call,
    ]

    assert mock_get_unique_nested_dicts.call_count == 1
    assert mock_list_users.call_count == 1

    assert mock_sync_identity_center_users.call_count == 0
    assert mock_sync_identity_center_groups.call_count == 0
    assert mock_logger.info.call_count == 20
    logger_calls = [call("synchronize:Found 3 Source Groups and 6 Users")]
    for group in source_groups:
        logger_calls.append(
            call(
                f"synchronize:Source:Group {group['name']} has {len(group['members'])} members"
            )
        )
    for user in source_users:
        logger_calls.append(call(f"synchronize:Source:User {user['primaryEmail']}"))
    logger_calls.append(call("synchronize:Found 3 Target Groups and 6 Users"))
    for group in target_groups:
        logger_calls.append(
            call(
                f"synchronize:Target:Group {group['DisplayName']} has {len(group['GroupMemberships'])} members"
            )
        )
    for user in target_users:
        logger_calls.append(call(f"synchronize:Target:User {user['UserName']}"))

    assert mock_logger.info.call_args_list == logger_calls


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.create_user")
def test_create_aws_users(
    mock_create_user, mock_logger, google_users, google_groups_w_users
):
    users_to_create = google_users(3)
    # groups_to_sync = google_groups_w_users(3, 9)
    mock_create_user.side_effect = users_to_create

    result = identity_center.create_aws_users(users_to_create)

    assert result == users_to_create
    assert mock_create_user.call_count == 3
    mock_logger.info.assert_any_call(
        f"create_aws_users:Starting creation of {len(users_to_create)} users."
    )
    for user in users_to_create:
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
        mock_logger.info.assert_any_call(
            f"create_aws_users:Successfully created user {user['primaryEmail']}"
        )
    assert (
        call("create_aws_users:Finished creation of 3 users.")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.DRY_RUN", True)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.create_user")
def test_create_aws_users_dry_run(mock_create_user, mock_logger, google_users):
    users_to_create = google_users(3)
    expected_output = [user["primaryEmail"] for user in users_to_create]

    result = identity_center.create_aws_users(users_to_create)

    assert result == expected_output
    assert mock_create_user.call_count == 0
    mock_logger.info.assert_any_call(
        f"create_aws_users:Starting creation of {len(users_to_create)} users."
    )
    for user in users_to_create:
        mock_logger.info.assert_any_call(
            f"create_aws_users:DRY_RUN:Successfully created user {user['primaryEmail']}"
        )
    assert (
        call("create_aws_users:Finished creation of 3 users.")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.create_user")
def test_create_aws_users_handles_failure(
    mock_create_user, mock_logger, google_users, aws_users
):
    users_to_create = google_users(3)
    created_users = aws_users(3)
    expected_output = [user["UserId"] for user in created_users]
    mock_create_user.side_effect = [expected_output[0], None, expected_output[2]]
    del expected_output[1]

    result = identity_center.create_aws_users(users_to_create)

    assert result == expected_output
    assert mock_create_user.call_count == 3
    assert mock_logger.info.call_count == 4
    assert mock_logger.error.call_count == 1
    mock_logger.info.assert_any_call(
        f"create_aws_users:Starting creation of {len(users_to_create)} users."
    )
    for i in range(len(users_to_create)):
        mock_create_user.assert_any_call(
            users_to_create[i]["primaryEmail"],
            users_to_create[i]["name"]["givenName"],
            users_to_create[i]["name"]["familyName"],
        )
        if i == 1:
            mock_logger.error.assert_any_call(
                f"create_aws_users:Failed to create user {users_to_create[i]['primaryEmail']}"
            )
        else:
            mock_logger.info.assert_any_call(
                f"create_aws_users:Successfully created user {users_to_create[i]['primaryEmail']}"
            )
    assert (
        call("create_aws_users:Finished creation of 2 users.")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.create_user")
def test_create_aws_users_empty_list(mock_create_user, mock_logger):
    users_to_create = []
    mock_create_user.side_effect = users_to_create

    result = identity_center.create_aws_users(users_to_create)

    assert result == users_to_create
    assert mock_create_user.call_count == 0
    assert mock_logger.info.call_count == 2
    assert (
        call("create_aws_users:Starting creation of 0 users.")
        in mock_logger.info.call_args_list
    )
    assert call("create_aws_users:Finished creation of 0 users.")


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
def test_delete_aws_users_default(mock_delete_user, mock_logger, aws_users):
    users_to_delete = aws_users(3)
    expected_output = [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]

    result = identity_center.delete_aws_users(users_to_delete)

    assert result == expected_output
    assert mock_logger.info.call_count == 5
    assert (
        call("delete_aws_users:Starting deletion of 3 users.")
        in mock_logger.info.call_args_list
    )
    for user in users_to_delete:
        mock_logger.info.assert_any_call(
            f"delete_aws_users:DRY_RUN:Successfully deleted user {user['UserName']}"
        )
    assert (
        call("delete_aws_users:Finished deletion of 3 users.")
        in mock_logger.info.call_args_list
    )
    mock_delete_user.call_count == 0


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
def test_delete_aws_users_enable_delete_true(mock_delete_user, mock_logger, aws_users):
    users_to_delete = aws_users(3)
    expected_output = [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]
    mock_delete_user.return_value = True

    result = identity_center.delete_aws_users(users_to_delete, enable_user_delete=True)

    assert result == expected_output
    assert mock_logger.info.call_count == 5
    assert (
        call("delete_aws_users:Starting deletion of 3 users.")
        in mock_logger.info.call_args_list
    )
    for user in users_to_delete:
        mock_logger.info.assert_any_call(
            f"delete_aws_users:Successfully deleted user {user['UserName']}"
        )
        mock_delete_user.assert_any_call(user["UserId"])
    assert (
        call("delete_aws_users:Finished deletion of 3 users.")
        in mock_logger.info.call_args_list
    )
    mock_delete_user.call_count == 3


@patch("modules.aws.identity_center.DRY_RUN", True)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
def test_delete_aws_users_enable_delete_true_dry_run(
    mock_delete_user, mock_logger, aws_users
):
    users_to_delete = aws_users(3)
    expected_output = [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]
    mock_delete_user.return_value = True

    result = identity_center.delete_aws_users(users_to_delete, enable_user_delete=True)

    assert result == expected_output
    assert mock_logger.info.call_count == 5
    assert (
        call("delete_aws_users:Starting deletion of 3 users.")
        in mock_logger.info.call_args_list
    )
    for user in users_to_delete:
        mock_logger.info.assert_any_call(
            f"delete_aws_users:DRY_RUN:Successfully deleted user {user['UserName']}"
        )
    assert (
        call("delete_aws_users:Finished deletion of 3 users.")
        in mock_logger.info.call_args_list
    )
    mock_delete_user.call_count == 0


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
def test_delete_aws_users_handles_failure(mock_delete_user, mock_logger, aws_users):
    users_to_delete = aws_users(3)
    expected_output = ["user-email1@test.com", "user-email3@test.com"]
    mock_delete_user.side_effect = [True, False, True]

    result = identity_center.delete_aws_users(users_to_delete, enable_user_delete=True)

    assert result == expected_output
    assert mock_logger.info.call_count == 4
    assert mock_logger.error.call_count == 1
    assert (
        call("delete_aws_users:Starting deletion of 3 users.")
        in mock_logger.info.call_args_list
    )
    for i in range(len(users_to_delete)):
        mock_delete_user.assert_any_call(users_to_delete[i]["UserId"])
        if i == 1:
            mock_logger.error.assert_any_call(
                f"delete_aws_users:Failed to delete user {users_to_delete[i]['UserName']}"
            )
        else:
            mock_logger.info.assert_any_call(
                f"delete_aws_users:Successfully deleted user {users_to_delete[i]['UserName']}"
            )
    assert (
        call("delete_aws_users:Finished deletion of 2 users.")
        in mock_logger.info.call_args_list
    )
    mock_delete_user.call_count == 3


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
def test_delete_aws_users_empty_list(mock_delete_user, mock_logger):
    users_to_delete = []
    mock_delete_user.side_effect = users_to_delete

    result = identity_center.delete_aws_users(users_to_delete)

    assert result == users_to_delete
    assert mock_delete_user.call_count == 0


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
@patch("modules.aws.identity_center.identity_store.create_user")
@patch("modules.aws.identity_center.entities.provision_entities")
@patch("modules.aws.identity_center.filters.compare_lists")
def test_sync_identity_center_users_default(
    mock_compare_lists,
    mock_provision_entities,
    mock_create_user,
    mock_delete_user,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)[:3]
    mock_compare_lists.return_value = source_users, target_users
    mock_provision_entities.side_effect = [source_users, []]

    result = identity_center.sync_users(source_users, target_users)

    assert result == (source_users, [])

    assert (
        call(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
        )
        in mock_compare_lists.call_args_list
    )
    assert (
        call(
            mock_create_user,
            source_users,
            execute=True,
            integration_name="aws",
            operation_name="creation",
            entity_name="user(s)",
            display_key="primaryEmail",
        )
        in mock_provision_entities.call_args_list
    )
    assert (
        call(
            mock_delete_user,
            target_users,
            execute=False,
            integration_name="aws",
            operation_name="deletion",
            entity_name="user(s)",
            display_key="UserName",
        )
    ) in mock_provision_entities.call_args_list
    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
@patch("modules.aws.identity_center.identity_store.create_user")
@patch("modules.aws.identity_center.entities.provision_entities")
@patch("modules.aws.identity_center.filters.compare_lists")
def test_sync_identity_center_users_enable_delete_true(
    mock_compare_lists,
    mock_provision_entities,
    mock_create_user,
    mock_delete_user,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)[:3]
    mock_compare_lists.return_value = source_users, target_users
    mock_provision_entities.side_effect = [source_users, target_users]

    result = identity_center.sync_users(
        source_users, target_users, enable_user_delete=True
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
    assert (
        call(
            mock_create_user,
            source_users,
            execute=True,
            integration_name="aws",
            operation_name="creation",
            entity_name="user(s)",
            display_key="primaryEmail",
        )
        in mock_provision_entities.call_args_list
    )
    assert (
        call(
            mock_delete_user,
            target_users,
            execute=True,
            integration_name="aws",
            operation_name="deletion",
            entity_name="user(s)",
            display_key="UserName",
        )
        in mock_provision_entities.call_args_list
    )
    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
@patch("modules.aws.identity_center.identity_store.create_user")
@patch("modules.aws.identity_center.entities.provision_entities")
@patch("modules.aws.identity_center.filters.compare_lists")
def test_sync_identity_center_users_delete_target_all_disable_delete(
    mock_compare_lists,
    mock_provision_entities,
    mock_create_user,
    mock_delete_user,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)
    mock_create_user.return_value = []
    mock_delete_user.return_value = target_users
    mock_provision_entities.side_effect = [[], target_users]

    result = identity_center.sync_users(
        source_users, target_users, delete_target_all=True
    )

    assert result == ([], target_users)
    assert mock_compare_lists.call_count == 0

    assert (
        call(
            mock_create_user,
            [],
            execute=True,
            integration_name="aws",
            operation_name="creation",
            entity_name="user(s)",
            display_key="primaryEmail",
        )
        in mock_provision_entities.call_args_list
    )
    assert (
        call(
            mock_delete_user,
            target_users,
            execute=False,
            integration_name="aws",
            operation_name="deletion",
            entity_name="user(s)",
            display_key="UserName",
        )
        in mock_provision_entities.call_args_list
    )

    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 0 Users to Create and 6 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_user")
@patch("modules.aws.identity_center.identity_store.create_user")
@patch("modules.aws.identity_center.entities.provision_entities")
@patch("modules.aws.identity_center.filters.compare_lists")
def test_sync_identity_center_users_delete_target_all_enable_delete(
    mock_compare_lists,
    mock_provision_entities,
    mock_create_user,
    mock_delete_user,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)
    mock_provision_entities.side_effect = [[], target_users]

    result = identity_center.sync_users(
        source_users,
        target_users,
        enable_user_create=True,
        enable_user_delete=True,
        delete_target_all=True,
    )

    assert result == ([], target_users)
    assert mock_compare_lists.call_count == 0

    assert (
        call(
            mock_create_user,
            [],
            execute=True,
            integration_name="aws",
            operation_name="creation",
            entity_name="user(s)",
            display_key="primaryEmail",
        )
        in mock_provision_entities.call_args_list
    )
    assert (
        call(
            mock_delete_user,
            target_users,
            execute=True,
            integration_name="aws",
            operation_name="deletion",
            entity_name="user(s)",
            display_key="UserName",
        )
        in mock_provision_entities.call_args_list
    )

    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 0 Users to Create and 6 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.filter_by_condition")
@patch("modules.aws.identity_center.identity_store.create_group_membership")
def test_create_group_memberships(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_users,
):
    group = aws_groups_w_users(1, 3)[0]
    target_users = aws_users(3)
    users_to_add = google_users(3)
    mock_filter_by_condition.side_effect = [
        [target_users[0]],
        [target_users[1]],
        [target_users[2]],
    ]

    mock_create_group_membership.side_effect = [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]

    result = identity_center.create_group_memberships(group, users_to_add, target_users)

    assert result == [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]
    assert mock_create_group_membership.call_count == 3
    assert mock_filter_by_condition.call_count == 3
    for user in target_users:
        assert (
            call(
                f"create_group_memberships:Successfully added user {user['UserName']} to group {group['DisplayName']}"
            )
            in mock_logger.info.call_args_list
        )
        mock_create_group_membership.assert_any_call(group["GroupId"], user["UserId"])


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.filter_by_condition")
@patch("modules.aws.identity_center.identity_store.create_group_membership")
def test_create_group_memberships_handles_failure(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_users,
):
    group = aws_groups_w_users(1, 3)[0]
    target_users = aws_users(3)
    users_to_add = google_users(3)
    mock_filter_by_condition.side_effect = [
        [target_users[0]],
        [target_users[1]],
        [target_users[2]],
    ]

    mock_create_group_membership.side_effect = [
        "user-email1@test.com",
        None,
        "user-email3@test.com",
    ]

    result = identity_center.create_group_memberships(group, users_to_add, target_users)

    assert result == [
        "user-email1@test.com",
        "user-email3@test.com",
    ]
    assert mock_create_group_membership.call_count == 3
    assert mock_filter_by_condition.call_count == 3
    for i in range(len(target_users)):
        if i == 1:
            assert (
                call(
                    f"create_group_memberships:Failed to add user {target_users[i]['UserName']} to group {group['DisplayName']}"
                )
                in mock_logger.error.call_args_list
            )
        else:
            assert (
                call(
                    f"create_group_memberships:Successfully added user {target_users[i]['UserName']} to group {group['DisplayName']}"
                )
                in mock_logger.info.call_args_list
            )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[i]["UserId"]
        )


@patch("modules.aws.identity_center.DRY_RUN", True)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.filter_by_condition")
@patch("modules.aws.identity_center.identity_store.create_group_membership")
def test_create_group_memberships_dry_run(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_users,
):
    group = aws_groups_w_users(1, 3)[0]
    target_users = aws_users(3)
    users_to_add = google_users(3)

    mock_filter_by_condition.side_effect = [
        [target_users[0]],
        [target_users[1]],
        [target_users[2]],
    ]
    result = identity_center.create_group_memberships(group, users_to_add, target_users)

    assert result == [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]
    assert mock_create_group_membership.call_count == 0
    assert mock_filter_by_condition.call_count == 3
    for user in target_users:
        mock_logger.info.assert_any_call(
            f"create_group_memberships:DRY_RUN:Successfully added user {user['UserName']} to group {group['DisplayName']}"
        )


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.filter_by_condition")
@patch("modules.aws.identity_center.identity_store.create_group_membership")
def test_create_group_memberships_empty_list(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups,
    aws_users,
):
    group = aws_groups(1)[0]
    target_users = aws_users(3)
    users_to_add = []

    result = identity_center.create_group_memberships(group, users_to_add, target_users)

    assert result == []
    assert mock_create_group_membership.call_count == 0
    assert mock_filter_by_condition.call_count == 0
    assert mock_logger.info.call_count == 2


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.filter_by_condition")
@patch("modules.aws.identity_center.identity_store.create_group_membership")
def test_create_group_memberships_matching_user_not_found(
    mock_create_group_membership,
    mock_filter_by_condition,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_users,
):
    group = aws_groups_w_users(1, 3)[0]
    target_users = aws_users(2)
    users_to_add = google_users(3)
    mock_filter_by_condition.side_effect = [
        [target_users[0]],
        [target_users[1]],
        [],
    ]

    mock_create_group_membership.side_effect = [
        "user-email1@test.com",
        "user-email2@test.com",
    ]

    result = identity_center.create_group_memberships(group, users_to_add, target_users)

    assert result == [
        "user-email1@test.com",
        "user-email2@test.com",
    ]
    assert mock_create_group_membership.call_count == 2

    for user in target_users:
        mock_logger.info.assert_any_call(
            f"create_group_memberships:Successfully added user {user['UserName']} to group {group['DisplayName']}"
        )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[0]["UserId"]
        )
        mock_create_group_membership.assert_any_call(
            group["GroupId"], target_users[1]["UserId"]
        )
    mock_logger.info.assert_any_call(
        f"create_group_memberships:Failed to find user {users_to_add[2]['primaryEmail']} in target system"
    )


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_group_membership")
def test_delete_group_memberships_defaults_not_deleting(
    mock_delete_group_membership,
    mock_logger,
    aws_groups_w_users,
):
    group = aws_groups_w_users(1, 6)[0]
    users_to_remove = group["GroupMemberships"]

    result = identity_center.delete_group_memberships(group, users_to_remove)

    assert result == [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        "user-email4@test.com",
        "user-email5@test.com",
        "user-email6@test.com",
    ]
    assert mock_delete_group_membership.call_count == 0
    mock_logger.info.assert_any_call(
        f"delete_group_memberships:Removing {len(users_to_remove)} users from group {group['DisplayName']}"
    )
    for user in users_to_remove:
        mock_logger.info.assert_any_call(
            f"delete_group_memberships:DRY_RUN:Successfully removed user {user['MemberId']['UserName']} from group {group['DisplayName']}"
        )

    assert mock_logger.info.call_count == 8


@patch("modules.aws.identity_center.DRY_RUN", True)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_group_membership")
def test_delete_group_memberships_enable_delete_dry_run(
    mock_delete_group_membership,
    mock_logger,
    aws_groups_w_users,
):
    group = aws_groups_w_users(1, 6)[0]
    users_to_remove = group["GroupMemberships"]

    mock_delete_group_membership.side_effect = [
        "membership_id_1",
        "membership_id_2",
        "membership_id_3",
        "membership_id_4",
        "membership_id_5",
        "membership_id_6",
    ]

    result = identity_center.delete_group_memberships(
        group, users_to_remove, enable_membership_delete=True
    )

    assert result == [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        "user-email4@test.com",
        "user-email5@test.com",
        "user-email6@test.com",
    ]
    assert mock_delete_group_membership.call_count == 0
    mock_logger.info.assert_any_call(
        f"delete_group_memberships:Removing {len(users_to_remove)} users from group {group['DisplayName']}"
    )
    for user in users_to_remove:
        mock_logger.info.assert_any_call(
            f"delete_group_memberships:DRY_RUN:Successfully removed user {user['MemberId']['UserName']} from group {group['DisplayName']}"
        )

    assert mock_logger.info.call_count == 8


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_group_membership")
def test_delete_group_memberships_enable_delete_and_not_dry_run(
    mock_delete_group_membership,
    mock_logger,
    aws_groups_w_users,
):
    group = aws_groups_w_users(1, 6)[0]
    users_to_remove = group["GroupMemberships"]

    mock_delete_group_membership.side_effect = [
        "membership_id_1",
        "membership_id_2",
        "membership_id_3",
        "membership_id_4",
        "membership_id_5",
        "membership_id_6",
    ]

    result = identity_center.delete_group_memberships(
        group, users_to_remove, enable_membership_delete=True
    )

    assert result == [
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        "user-email4@test.com",
        "user-email5@test.com",
        "user-email6@test.com",
    ]
    assert mock_delete_group_membership.call_count == 6
    mock_logger.info.assert_any_call(
        f"delete_group_memberships:Removing {len(users_to_remove)} users from group {group['DisplayName']}"
    )
    for user in users_to_remove:
        mock_logger.info.assert_any_call(
            f"delete_group_memberships:Successfully removed user {user['MemberId']['UserName']} from group {group['DisplayName']}"
        )

    assert mock_logger.info.call_count == 8


@patch("modules.aws.identity_center.DRY_RUN", False)
@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store.delete_group_membership")
def test_delete_group_memberships_handles_failure(
    mock_delete_group_membership,
    mock_logger,
    aws_groups_w_users,
):
    group = aws_groups_w_users(1, 6)[0]
    users_to_remove = group["GroupMemberships"]

    mock_delete_group_membership.side_effect = [
        "membership_id_1",
        None,
        "membership_id_3",
        None,
        "membership_id_5",
        "membership_id_6",
    ]

    result = identity_center.delete_group_memberships(
        group, users_to_remove, enable_membership_delete=True
    )

    assert result == [
        "user-email1@test.com",
        "user-email3@test.com",
        "user-email5@test.com",
        "user-email6@test.com",
    ]
    assert mock_delete_group_membership.call_count == 6
    for i in range(len(users_to_remove)):
        if i == 1 or i == 3:
            mock_logger.error.assert_any_call(
                f"delete_group_memberships:Failed to remove user {users_to_remove[i]['MemberId']['UserName']} from group {group['DisplayName']}"
            )
        else:
            mock_logger.info.assert_any_call(
                f"delete_group_memberships:Successfully removed user {users_to_remove[i]['MemberId']['UserName']} from group {group['DisplayName']}"
            )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.compare_lists")
@patch("modules.aws.identity_center.create_group_memberships")
@patch("modules.aws.identity_center.delete_group_memberships")
def test_sync_identity_center_groups_defaults(
    mock_delete_group_memberships,
    mock_create_group_memberships,
    mock_compare_lists,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
):
    source_groups = google_groups_w_users(3, 6, group_prefix="target-")
    for group in source_groups:
        group["members"] = group["members"][:3]
        group["DisplayName"] = group["name"]
    target_groups = aws_groups_w_users(3, 6, group_prefix="target-")
    for group in target_groups:
        group["GroupMemberships"] = group["GroupMemberships"][3:]
    target_users = aws_users(6)

    side_effects = [
        (source_groups, target_groups),
        (source_groups[0]["members"], target_groups[0]["GroupMemberships"]),
        (source_groups[1]["members"], target_groups[1]["GroupMemberships"]),
        (source_groups[2]["members"], target_groups[2]["GroupMemberships"]),
    ]
    mock_compare_lists.side_effect = side_effects
    mock_create_group_memberships.side_effect = [
        ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
        ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
        ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
    ]
    mock_delete_group_memberships.side_effect = [
        [],
        [],
        [],
    ]
    result = identity_center.sync_groups(source_groups, target_groups, target_users)

    assert result == (
        [
            "target-membership_id_1",
            "target-membership_id_2",
            "target-membership_id_3",
            "target-membership_id_1",
            "target-membership_id_2",
            "target-membership_id_3",
            "target-membership_id_1",
            "target-membership_id_2",
            "target-membership_id_3",
        ],
        [],
    )
    assert (
        call(
            {"values": source_groups, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_compare_lists.call_args_list
    )
    assert mock_compare_lists.call_count == 4
    assert mock_create_group_memberships.call_count == 3
    assert mock_delete_group_memberships.call_count == 3
    assert mock_logger.info.call_count == 4
    assert (
        call("synchronize:groups:Found 3 Source Groups and 3 Target Groups")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.compare_lists")
@patch("modules.aws.identity_center.create_group_memberships")
@patch("modules.aws.identity_center.delete_group_memberships")
def test_sync_identity_center_groups_enable_delete_true(
    mock_delete_group_memberships,
    mock_create_group_memberships,
    mock_compare_lists,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
):
    source_groups = google_groups_w_users(3, 6, group_prefix="target-")
    for group in source_groups:
        group["members"] = group["members"][:3]
        group["DisplayName"] = group["name"]
    target_groups = aws_groups_w_users(3, 6, group_prefix="target-")
    for group in target_groups:
        group["GroupMemberships"] = group["GroupMemberships"][3:]
    target_users = aws_users(6)

    side_effects = [
        (source_groups, target_groups),
        (source_groups[0]["members"], target_groups[0]["GroupMemberships"]),
        (source_groups[1]["members"], target_groups[1]["GroupMemberships"]),
        (source_groups[2]["members"], target_groups[2]["GroupMemberships"]),
    ]
    mock_compare_lists.side_effect = side_effects
    mock_create_group_memberships.side_effect = [
        ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
        ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
        ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
    ]
    mock_delete_group_memberships.side_effect = [
        ["target-membership_id_4", "target-membership_id_5", "target-membership_id_6"],
        ["target-membership_id_4", "target-membership_id_5", "target-membership_id_6"],
        ["target-membership_id_4", "target-membership_id_5", "target-membership_id_6"],
    ]
    result = identity_center.sync_groups(
        source_groups, target_groups, target_users, enable_delete=True
    )

    assert result == (
        [
            "target-membership_id_1",
            "target-membership_id_2",
            "target-membership_id_3",
            "target-membership_id_1",
            "target-membership_id_2",
            "target-membership_id_3",
            "target-membership_id_1",
            "target-membership_id_2",
            "target-membership_id_3",
        ],
        [
            "target-membership_id_4",
            "target-membership_id_5",
            "target-membership_id_6",
            "target-membership_id_4",
            "target-membership_id_5",
            "target-membership_id_6",
            "target-membership_id_4",
            "target-membership_id_5",
            "target-membership_id_6",
        ],
    )
    assert (
        call(
            {"values": source_groups, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_compare_lists.call_args_list
    )
    assert mock_compare_lists.call_count == 4
    assert mock_create_group_memberships.call_count == 3
    assert mock_delete_group_memberships.call_count == 3
    assert mock_logger.info.call_count == 4
    assert (
        call("synchronize:groups:Found 3 Source Groups and 3 Target Groups")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.compare_lists")
@patch("modules.aws.identity_center.create_group_memberships")
@patch("modules.aws.identity_center.delete_group_memberships")
def test_sync_identity_center_groups_empty_source_groups(
    mock_delete_group_memberships,
    mock_create_group_memberships,
    mock_compare_lists,
    mock_logger,
    aws_groups_w_users,
    aws_users,
):
    source_groups = []
    target_groups = aws_groups_w_users(3, 3, group_prefix="target-")
    target_users = aws_users(3)
    mock_compare_lists.return_value = [], []

    result = identity_center.sync_groups(
        source_groups, target_groups, target_users, enable_delete=True
    )

    assert result == ([], [])
    assert (
        call(
            {"values": source_groups, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_compare_lists.call_args_list
    )
    assert mock_compare_lists.call_count == 1
    assert mock_create_group_memberships.call_count == 0
    assert mock_delete_group_memberships.call_count == 0
    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:groups:Found 0 Source Groups and 0 Target Groups")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.compare_lists")
@patch("modules.aws.identity_center.create_group_memberships")
@patch("modules.aws.identity_center.delete_group_memberships")
def test_sync_identity_center_groups_empty_target_groups(
    mock_delete_group_memberships,
    mock_create_group_memberships,
    mock_compare_lists,
    mock_logger,
    aws_users,
    google_groups_w_users,
):
    source_groups = google_groups_w_users(3, 3, group_prefix="source-")
    target_groups = []
    target_users = aws_users(3)
    mock_compare_lists.return_value = [], []

    result = identity_center.sync_groups(
        source_groups, target_groups, target_users, enable_delete=True
    )

    assert result == ([], [])
    assert (
        call(
            {"values": source_groups, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_compare_lists.call_args_list
    )
    assert mock_compare_lists.call_count == 1
    assert mock_create_group_memberships.call_count == 0
    assert mock_delete_group_memberships.call_count == 0
    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:groups:Found 0 Source Groups and 0 Target Groups")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters.compare_lists")
@patch("modules.aws.identity_center.create_group_memberships")
@patch("modules.aws.identity_center.delete_group_memberships")
def test_sync_identity_center_groups_no_matching_groups_to_sync(
    mock_delete_group_memberships,
    mock_create_group_memberships,
    mock_compare_lists,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
):
    source_groups = google_groups_w_users(3, 3, group_prefix="source-")
    target_groups = aws_groups_w_users(3, 3, group_prefix="target-")
    target_users = aws_users(3)
    mock_compare_lists.return_value = [], []

    result = identity_center.sync_groups(
        source_groups, target_groups, target_users, enable_delete=True
    )

    assert result == ([], [])
    assert (
        call(
            {"values": source_groups, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_compare_lists.call_args_list
    )
    assert mock_compare_lists.call_count == 1
    assert mock_create_group_memberships.call_count == 0
    assert mock_delete_group_memberships.call_count == 0
    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:groups:Found 0 Source Groups and 0 Target Groups")
        in mock_logger.info.call_args_list
    )
