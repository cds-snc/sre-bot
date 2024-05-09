from unittest.mock import MagicMock, call, patch
from modules.provisioning import users


@patch("modules.provisioning.users.logger")
def test_provision_entities_success(mock_logger):
    users_list = [{"name": "user1"}, {"name": "user2"}, {"name": "user3"}]
    mock_function = MagicMock()
    mock_function.return_value = True

    result = users.provision_entities(
        mock_function,
        users_list,
        integration_name="aws",
        operation_name="creation",
        display_key="name",
    )

    assert len(result) == len(users_list)
    assert mock_function.call_count == len(users_list)
    mock_logger.info.assert_any_call("aws:Starting creation of 3 entity(ies)")
    for user in users_list:
        mock_logger.info.assert_any_call(
            f"aws:Successful creation of entity(ies) {user['name']}"
        )
    mock_logger.error.assert_not_called()


@patch("modules.provisioning.users.logger")
def test_provision_entities_failure(mock_logger):
    mock_function = MagicMock()
    users_list = [{"name": "user1"}, {"name": "user2"}, {"name": "user3"}]
    mock_function.side_effect = [True, False, True]

    result = users.provision_entities(
        mock_function,
        users_list,
        integration_name="aws",
        operation_name="creation",
        display_key="name",
    )

    assert len(result) == 2
    assert mock_function.call_count == len(users_list)

    info_calls = [
        call("aws:Starting creation of 3 entity(ies)"),
        call("aws:Successful creation of entity(ies) user1"),
        call("aws:Successful creation of entity(ies) user3"),
        call("aws:Completed creation of 2 entity(ies)"),
    ]

    assert mock_logger.info.call_args_list == info_calls
    assert mock_logger.error.call_args_list == [
        call("aws:Failed creation of entity(ies) user2")
    ]


@patch("modules.provisioning.users.logger")
def test_provision_entities_empty_list(mock_logger):
    users_list = []
    mock_function = MagicMock()
    result = users.provision_entities(
        mock_function,
        users_list,
        integration_name="aws",
        operation_name="creation",
        display_key="name",
    )

    assert len(result) == 0
    assert mock_function.call_count == 0
    mock_logger.info.assert_any_call("aws:Starting creation of 0 entity(ies)")
    mock_logger.info.assert_any_call("aws:Completed creation of 0 entity(ies)")
    mock_logger.error.assert_not_called()
