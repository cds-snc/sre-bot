from unittest.mock import MagicMock, patch
from modules.provisioning import users


def test_get_unique_users_from_groups(google_groups_w_users):
    groups = google_groups_w_users()
    unique_users = []
    for group in groups:
        for user in group["members"]:
            if user not in unique_users:
                unique_users.append(user)
    users_from_groups = users.get_unique_users_from_groups(groups, "members")

    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        unique_users, key=lambda user: user["id"]
    )


def test_get_unique_users_from_groups_with_empty_groups():
    groups = []
    users_from_groups = users.get_unique_users_from_groups(groups, "members")
    assert users_from_groups == []


def test_get_unique_users_from_dict_group(google_groups_w_users):
    source_group = google_groups_w_users()[0]
    users_from_groups = users.get_unique_users_from_groups(source_group, "members")
    expected_users = source_group["members"]
    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        expected_users, key=lambda user: user["id"]
    )


def test_get_unique_users_from_dict_group_with_duplicate_key():
    group = {
        "id": "source_group_id1",
        "name": "SOURCE-group1",
        "email": "SOURCE-group1@test.com",
        "members": [
            {"email": "user1.test@test.com", "id": "user1_id", "username": "user1"},
            {"email": "user2.test@test.com", "id": "user2_id", "username": "user1"},
            {"email": "user3.test@test.com", "id": "user3_id", "username": "user2"},
        ],
    }
    users_from_groups = users.get_unique_users_from_groups(group, "members")
    expected_users = [
        {"email": "user1.test@test.com", "id": "user1_id", "username": "user1"},
        {"email": "user2.test@test.com", "id": "user2_id", "username": "user1"},
        {"email": "user3.test@test.com", "id": "user3_id", "username": "user2"},
    ]
    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        expected_users, key=lambda user: user["id"]
    )


@patch("modules.provisioning.users.logger")
def test_provision_users_success(mock_logger):
    users_list = [{"name": "user1"}, {"name": "user2"}, {"name": "user3"}]
    mock_function = MagicMock()
    mock_function.return_value = True

    result = users.provision_users("aws", "creation", mock_function, users_list, "name")

    assert len(result) == len(users_list)
    assert mock_function.call_count == len(users_list)
    mock_logger.info.assert_any_call("aws:Starting creation of 3 user(s)")
    for user in users_list:
        mock_logger.info.assert_any_call(f"user's data:\n{user}")
        mock_logger.info.assert_any_call(
            f"aws:Successful creation of user {user['name']}"
        )
    mock_logger.error.assert_not_called()


@patch("modules.provisioning.users.logger")
def test_provision_users_failure(mock_logger):
    mock_function = MagicMock()
    users_list = [{"name": "user1"}, {"name": "user2"}, {"name": "user3"}]
    mock_function.side_effect = [True, False, True]

    result = users.provision_users("aws", "creation", mock_function, users_list, "name")

    assert len(result) == 2
    assert mock_function.call_count == len(users_list)
    mock_logger.info.assert_any_call("aws:Starting creation of 3 user(s)")
    for i in range(len(users_list)):
        mock_logger.info.assert_any_call(f"user's data:\n{users_list[i]}")
        if i == 1:
            mock_logger.error.assert_any_call(
                f"aws:Failed creation user {users_list[i]['name']}"
            )
        else:
            mock_logger.info.assert_any_call(
                f"aws:Successful creation of user {users_list[i]['name']}"
            )


@patch("modules.provisioning.users.logger")
def test_provision_users_empty_list(mock_logger):
    users_list = []
    mock_function = MagicMock()
    result = users.provision_users("aws", "creation", mock_function, users_list, "name")

    assert len(result) == 0
    assert mock_function.call_count == 0
    mock_logger.info.assert_any_call("aws:Starting creation of 0 user(s)")
    mock_logger.error.assert_not_called()
