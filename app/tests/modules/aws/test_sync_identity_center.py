from unittest.mock import patch, call
from pytest import fixture
from modules.aws import sync_identity_center


# @fixture
# def aws_groups():
#     return [
#         {
#             "GroupId": "aws_group_id1",
#             "DisplayName": "group1",
#         },
#         {
#             "GroupId": "aws_group_id2",
#             "DisplayName": "group2",
#         },
#     ]


# @fixture
# def aws_users():
#     return [
#         {
#             "UserName": "user1.test@test.com",
#             "UserId": "user1_id",
#             "Name": {"GivenName": "User1", "FamilyName": "Test"},
#         },
#         {
#             "UserName": "user2.test@test.com",
#             "UserId": "user2_id",
#             "Name": {"GivenName": "User2", "FamilyName": "Test"},
#         },
#     ]


# @fixture
# def aws_missing_users():
#     return [
#         {
#             "UserName": "user4.test@test.com",
#             "UserId": "user4_id",
#             "Name": {"GivenName": "User4", "FamilyName": "Test"},
#         },
#         {
#             "UserName": "user5.test@test.com",
#             "UserId": "user5_id",
#             "Name": {"GivenName": "User5", "FamilyName": "Test"},
#         },
#     ]


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
