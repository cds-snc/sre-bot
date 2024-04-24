from unittest.mock import patch
from pytest import fixture
from modules.aws import sync_identity_center


@fixture
def google_groups():
    return [
        {
            "id": "google_group_id1",
            "name": "AWS-group1",
            "email": "aws-group1@test.com",
        },
        {
            "id": "google_group_id2",
            "name": "AWS-group2",
            "email": "aws-group2@test.com",
        },
        {"id": "google_group_id3", "name": "AWSgroup3", "email": "awsgroup3@test.com"},
    ]


@fixture
def google_groups_w_users():
    return [
        {
            "id": "google_group_id1",
            "name": "AWS-group1",
            "email": "aws-group1@test.com",
            "members": [
                {"email": "user1.test@test.com", "id": "user1_id"},
                {"email": "user2.test@test.com", "id": "user2_id"},
                {"email": "user3.test@test.com", "id": "user3_id"},
            ],
        },
        {
            "id": "google_group_id2",
            "name": "AWS-group2",
            "email": "aws-group2@test.com",
            "members": [
                {"email": "user1.test@test.com", "id": "user1_id"},
                {"email": "user2.test@test.com", "id": "user2_id"},
                {"email": "user9.test@external.com", "id": "user9_external_id"},
            ],
        },
        {
            "id": "google_group_id3",
            "name": "AWSgroup3",
            "email": "awsgroup3@test.com",
            "members": [],
        },
    ]


@fixture
def aws_groups():
    return [
        {
            "GroupId": "aws_group_id1",
            "DisplayName": "group1",
        },
        {
            "GroupId": "aws_group_id2",
            "DisplayName": "group2",
        },
    ]


@fixture
def aws_users():
    return [
        {
            "UserName": "user1.test@test.com",
            "UserId": "user1_id",
            "Name": {"GivenName": "User1", "FamilyName": "Test"},
        },
        {
            "UserName": "user2.test@test.com",
            "UserId": "user2_id",
            "Name": {"GivenName": "User2", "FamilyName": "Test"},
        },
    ]


@patch("modules.aws.sync_identity_center.google_directory.list_groups")
@patch("modules.aws.sync_identity_center.filter_by_condition")
def test_get_source_groups(
    mock_filter_by_condition,
    mock_google_directory_list_groups,
    google_groups,
):
    mock_google_directory_list_groups.return_value = google_groups
    mock_filter_by_condition.return_value = google_groups

    result = sync_identity_center.get_source_groups()

    assert result == google_groups
    assert mock_google_directory_list_groups.called_with("email:aws-*")
    assert mock_filter_by_condition.called_with(
        google_groups, lambda group: "AWS-" in group["name"]
    )


@patch("modules.aws.sync_identity_center.google_directory.add_users_to_group")
@patch("modules.aws.sync_identity_center.get_source_groups")
def test_get_source_groups_with_users(
    mock_get_source_groups,
    mock_add_users_to_group,
    google_groups,
    google_groups_w_users,
):
    # Setup the mock functions
    mock_get_source_groups.return_value = google_groups

    mock_add_users_to_group.side_effect = [
        google_groups_w_users[0],
        google_groups_w_users[1],
        google_groups_w_users[2],
    ]

    # Call the function
    result = sync_identity_center.get_source_groups_with_users()

    # Check the results
    assert result == google_groups_w_users

    # Check the calls
    # Check the calls
    assert mock_get_source_groups.called
    assert mock_add_users_to_group.call_count == 3


# def test_filter_users_by_condition(google_groups):
#     condition = []
#     result = sync_identity_center.filter_users_by_condition(
#         google_groups[1]["members"], condition
#     )


# @patch("modules.aws.sync_identity_center.identity_store.create_user")
# @patch("modules.aws.sync_identity_center.identity_store.list_users")
# @patch("modules.aws.sync_identity_center.google_directory.get_user")
# @patch("modules.aws.sync_identity_center.google_directory.list_group_members")
# @patch("modules.aws.sync_identity_center.google_directory.list_groups")
# def test_sync_users(
#     mock_google_directory_list_groups,
#     mock_google_directory_list_group_members,
#     mock_google_directory_get_user,
#     mock_identity_store_list_users,
#     mock_identity_store_create_user,
#     google_groups,
#     aws_users,
# ):
#     mock_google_directory_list_groups.return_value = google_groups
#     mock_google_directory_list_group_members.return_value = google_groups[1]["members"]
#     mock_identity_store_list_users.return_value = aws_users
#     mock_identity_store_create_user.return_value = "new_user_id"

#     sync_identity_center.sync_users()

#     assert mock_google_directory_list_groups.called_with("email:aws-*")
#     assert mock_identity_store_list_users.called
#     assert mock_google_directory_list_group_members.called
#     # assert mock_identity_store_create_user.called
