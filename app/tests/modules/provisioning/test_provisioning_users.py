from unittest.mock import MagicMock, patch
from modules.provisioning import users


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
