from unittest.mock import patch, call
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
def google_groups_unique_users():
    return [
        {
            "email": "user1.test@test.com",
            "id": "user1_id",
            "name": {
                "displayName": "User1 Test",
                "givenName": "User1",
                "familyName": "Test",
            },
        },
        {
            "email": "user2.test@test.com",
            "id": "user2_id",
            "name": {
                "displayName": "User2 Test",
                "givenName": "User2",
                "familyName": "Test",
            },
        },
        {
            "email": "user3.test@test.com",
            "id": "user3_id",
            "name": {
                "displayName": "User3 Test",
                "givenName": "User3",
                "familyName": "Test",
            },
        },
        {
            "email": "user9.test@external.com",
            "id": "user9_external_id",
            "name": {
                "displayName": "User9 External",
                "givenName": "User9",
                "familyName": "External",
            },
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


@fixture
def aws_missing_users():
    return [
        {
            "UserName": "user4.test@test.com",
            "UserId": "user4_id",
            "Name": {"GivenName": "User4", "FamilyName": "Test"},
        },
        {
            "UserName": "user5.test@test.com",
            "UserId": "user5_id",
            "Name": {"GivenName": "User5", "FamilyName": "Test"},
        },
    ]


@patch("modules.aws.sync_identity_center.sync_aws_groups_members")
@patch("modules.aws.sync_identity_center.sync_aws_users")
@patch("modules.aws.sync_identity_center.get_source_groups_with_users")
@patch("modules.aws.sync_identity_center.get_unique_users_from_groups")
@patch("modules.aws.sync_identity_center.identity_store.list_users")
@patch("modules.aws.sync_identity_center.identity_store.list_groups_with_memberships")
def test_synchronize_with_defaults(
    mock_identity_store_list_groups_with_memberships,
    mock_identity_store_list_users,
    mock_get_unique_users_from_groups,
    mock_get_source_groups_with_users,
    mock_sync_aws_users,
    mock_sync_aws_groups_members,
):
    result = sync_identity_center.synchronize()

    assert result == (None, None)

    assert mock_identity_store_list_groups_with_memberships.not_called
    assert mock_identity_store_list_users.not_called
    assert mock_get_unique_users_from_groups.not_called
    assert mock_get_source_groups_with_users.called
    assert mock_sync_aws_users.not_called
    assert mock_sync_aws_groups_members.not_called


@patch("modules.aws.sync_identity_center.sync_aws_groups_members")
@patch("modules.aws.sync_identity_center.sync_aws_users")
@patch("modules.aws.sync_identity_center.get_source_groups_with_users")
@patch("modules.aws.sync_identity_center.get_unique_users_from_groups")
@patch("modules.aws.sync_identity_center.identity_store.list_users")
@patch("modules.aws.sync_identity_center.identity_store.list_groups_with_memberships")
def test_synchronize_with_sync_users_true(
    mock_identity_store_list_groups_with_memberships,
    mock_identity_store_list_users,
    mock_get_unique_users_from_groups,
    mock_get_source_groups_with_users,
    mock_sync_aws_users,
    mock_sync_aws_groups_members,
    google_groups_w_users,
    google_groups_unique_users,
    aws_users,
):
    mock_get_source_groups_with_users.return_value = google_groups_w_users
    mock_get_unique_users_from_groups.return_value = google_groups_unique_users
    mock_identity_store_list_users.return_value = aws_users
    mock_sync_aws_users.return_value = "users_sync_status"
    result = sync_identity_center.synchronize(sync_users=True)

    assert result == ("users_sync_status", None)

    assert mock_identity_store_list_groups_with_memberships.not_called
    assert mock_identity_store_list_users.called
    assert mock_get_unique_users_from_groups.called_with(
        google_groups_w_users, "members"
    )
    assert mock_get_source_groups_with_users.called_with("email:aws-*")
    assert mock_sync_aws_users.called_with(google_groups_unique_users, aws_users)
    assert mock_sync_aws_groups_members.not_called


@patch("modules.aws.sync_identity_center.sync_aws_groups_members")
@patch("modules.aws.sync_identity_center.sync_aws_users")
@patch("modules.aws.sync_identity_center.get_source_groups_with_users")
@patch("modules.aws.sync_identity_center.get_unique_users_from_groups")
@patch("modules.aws.sync_identity_center.identity_store.list_users")
@patch("modules.aws.sync_identity_center.identity_store.list_groups_with_memberships")
def test_synchronize_with_sync_groups_true(
    mock_identity_store_list_groups_with_memberships,
    mock_identity_store_list_users,
    mock_get_unique_users_from_groups,
    mock_get_source_groups_with_users,
    mock_sync_aws_users,
    mock_sync_aws_groups_members,
    google_groups_w_users,
    google_groups_unique_users,
    aws_users,
    aws_groups,
):
    mock_get_source_groups_with_users.return_value = google_groups_w_users
    mock_get_unique_users_from_groups.return_value = google_groups_unique_users
    mock_identity_store_list_users.return_value = aws_users
    mock_sync_aws_groups_members.return_value = "groups_sync_status"
    result = sync_identity_center.synchronize(sync_groups=True)

    assert result == (None, "groups_sync_status")

    assert mock_identity_store_list_groups_with_memberships.called
    assert mock_identity_store_list_users.not_called
    assert mock_get_unique_users_from_groups.not_called
    assert mock_get_source_groups_with_users.called_with("email:aws-*")
    assert mock_sync_aws_users.not_called
    assert mock_sync_aws_groups_members.called_with(google_groups_w_users, aws_groups)


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


@patch("modules.aws.sync_identity_center.identity_store.create_user")
@patch("modules.aws.sync_identity_center.logger")
def test_create_users_with_users_list(
    mock_logger, mock_create_user, google_groups_unique_users
):
    mock_create_user.side_effect = [
        "user1_id",
        "user2_id",
        "user3_id",
        "user9_external_id",
    ]
    response = sync_identity_center.create_aws_users(google_groups_unique_users)

    assert response == ["user1_id", "user2_id", "user3_id", "user9_external_id"]

    assert mock_create_user.call_count == 4
    assert mock_logger.info.call_count == 4
    assert mock_logger.info.call_args_list == [
        call("Creating user User1 Test"),
        call("Creating user User2 Test"),
        call("Creating user User3 Test"),
        call("Creating user User9 External"),
    ]


@patch("modules.aws.sync_identity_center.identity_store.create_user")
def test_create_users_with_empty_users_list(mock_create_user):
    result = sync_identity_center.create_aws_users([])
    assert result == []

    assert mock_create_user.call_count == 0


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
