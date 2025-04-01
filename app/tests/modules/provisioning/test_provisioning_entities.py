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
        call(
            "provision_entities_started",
            integration="aws",
            entity="Entity",
            operation="creation",
            entities_count=3,
        ),
        call(
            "provision_entity_successful",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user1",
        ),
        call(
            "provision_entity_successful",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user2",
        ),
        call(
            "provision_entity_successful",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user3",
        ),
        call(
            "provision_entities_completed",
            integration="aws",
            entity="Entity",
            operation="creation",
            provisioned_entities_count=3,
        ),
    ]

    mock_logger.info.assert_has_calls(info_calls)
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
        call(
            "provision_entities_started",
            integration="aws",
            entity="Entity",
            operation="creation",
            entities_count=3,
        ),
        call(
            "provision_entity_successful",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user1",
        ),
        call(
            "provision_entity_successful",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user3",
        ),
        call(
            "provision_entities_completed",
            integration="aws",
            entity="Entity",
            operation="creation",
            provisioned_entities_count=2,
        ),
    ]

    mock_logger.info.assert_has_calls(info_calls)
    mock_logger.error.assert_has_calls(
        [
            call(
                "provision_entity_failed",
                integration="aws",
                entity="Entity",
                operation="creation",
                entity_value="user2",
            )
        ]
    )
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
    mock_logger.info.assert_has_calls(
        [
            call(
                "provision_entities_no_entities_to_process",
                integration="aws",
                entity="Entity",
                operation="creation",
            )
        ]
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
        call(
            "provision_entities_started",
            integration="aws",
            entity="Entity",
            operation="creation",
            entities_count=3,
        ),
        call(
            "provision_entity_dry_run",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user1",
        ),
        call(
            "provision_entity_dry_run",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user2",
        ),
        call(
            "provision_entity_dry_run",
            integration="aws",
            entity="Entity",
            operation="creation",
            entity_value="user3",
        ),
        call(
            "provision_entities_completed",
            integration="aws",
            entity="Entity",
            operation="creation",
            provisioned_entities_count=3,
        ),
    ]

    mock_logger.info.assert_has_calls(info_calls)
    mock_log_to_sentinel.assert_called()
