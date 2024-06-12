from unittest.mock import MagicMock, call, patch
from modules.provisioning import entities


@patch("modules.provisioning.entities.log_to_sentinel")
@patch("modules.provisioning.entities.logger")
def test_provision_entities_success(mock_logger, mock_log_to_sentinel):
    users_list = [{"name": "user1"}, {"name": "user2"}, {"name": "user3"}]
    mock_function = MagicMock()
    mock_function.return_value = True

    result = entities.provision_entities(
        mock_function,
        users_list,
        integration_name="aws",
        operation_name="creation",
        display_key="name",
    )

    assert len(result) == len(users_list)
    assert mock_function.call_count == len(users_list)
    info_calls = [
        call("aws:Entity:creation: Started processing 3 entities"),
        call("aws:Entity:creation: Completed processing 3 entities"),
    ]
    for i, user in enumerate(users_list):
        pos = i + 1
        info_calls.insert(pos, call(f"aws:Entity:creation:Successful: {user['name']}"))

    assert mock_logger.info.call_args_list == info_calls
    mock_logger.error.assert_not_called()
    mock_log_to_sentinel.assert_called()


@patch("modules.provisioning.entities.log_to_sentinel")
@patch("modules.provisioning.entities.logger")
def test_provision_entities_failure(mock_logger, mock_log_to_sentinel):
    mock_function = MagicMock()
    users_list = [{"name": "user1"}, {"name": "user2"}, {"name": "user3"}]
    mock_function.side_effect = [True, False, True]

    result = entities.provision_entities(
        mock_function,
        users_list,
        integration_name="aws",
        operation_name="creation",
        display_key="name",
    )

    assert len(result) == 2
    assert mock_function.call_count == len(users_list)

    info_calls = [
        call("aws:Entity:creation: Started processing 3 entities"),
        call("aws:Entity:creation:Successful: user1"),
        call("aws:Entity:creation:Successful: user3"),
        call("aws:Entity:creation: Completed processing 2 entities"),
    ]

    assert mock_logger.info.call_args_list == info_calls
    assert mock_logger.error.call_args_list == [
        call("aws:Entity:creation:Failed: user2"),
    ]
    mock_log_to_sentinel.assert_called()


@patch("modules.provisioning.entities.log_to_sentinel")
@patch("modules.provisioning.entities.logger")
def test_provision_entities_empty_list(mock_logger, mock_log_to_sentinel):
    users_list = []
    mock_function = MagicMock()
    result = entities.provision_entities(
        mock_function,
        users_list,
        integration_name="aws",
        operation_name="creation",
        display_key="name",
    )

    assert len(result) == 0
    assert mock_function.call_count == 0
    assert (
        call("aws:Entity:creation: No entities to process")
        in mock_logger.info.call_args_list
    )
    mock_logger.error.assert_not_called()
    mock_log_to_sentinel.assert_not_called()


@patch("modules.provisioning.entities.log_to_sentinel")
@patch("modules.provisioning.entities.logger")
def test_provision_entities_execute_false(mock_logger, mock_log_to_sentinel):
    mock_function = MagicMock()
    users_list = [{"name": "user1"}, {"name": "user2"}, {"name": "user3"}]
    mock_function.side_effect = [True, True, True]

    result = entities.provision_entities(
        mock_function,
        users_list,
        execute=False,
        integration_name="aws",
        operation_name="creation",
        display_key="name",
    )

    assert len(result) == 3
    assert mock_function.call_count == 0

    info_calls = [
        call("aws:Entity:creation: Started processing 3 entities"),
        call("aws:Entity:creation:Successful:DRY_RUN: user1"),
        call("aws:Entity:creation:Successful:DRY_RUN: user2"),
        call("aws:Entity:creation:Successful:DRY_RUN: user3"),
        call("aws:Entity:creation: Completed processing 3 entities"),
    ]

    assert mock_logger.info.call_args_list == info_calls
    mock_log_to_sentinel.assert_called()
