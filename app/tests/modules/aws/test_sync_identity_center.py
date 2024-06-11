from unittest.mock import patch, call, ANY, MagicMock
from pytest import fixture, raises

from modules.aws import identity_center


@fixture
def provision_entities_side_effect_fixture(mock_identity_store):
    def _provision_entities_side_effect(function, entities, **kwargs):
        entities_provisioned = []
        function_name = function._mock_name.split(".")[-1]
        execute = kwargs.get("execute", True)
        for entity in entities:
            if function_name == "create_user":
                entities_provisioned.append(
                    {
                        "entity": entity["primaryEmail"],
                        "response": {entity["primaryEmail"] if execute else None},
                    }
                )
            elif function_name == "delete_user":
                entities_provisioned.append(
                    {
                        "entity": entity["UserName"],
                        "response": kwargs.get("execute", True),
                    }
                )
            elif function_name == "create_group_membership":
                entities_provisioned.append(
                    {
                        "entity": entity["primaryEmail"],
                        "response": (
                            f"membership-{entity['primaryEmail']}" if execute else None
                        ),
                    }
                )
            elif function_name == "delete_group_membership":
                entities_provisioned.append(
                    {
                        "entity": entity["MemberId"]["UserName"],
                        "response": kwargs.get("execute", False),
                    }
                )
        return entities_provisioned

    return _provision_entities_side_effect


@fixture
def provision_entities_calls_fixture():
    def _provision_entities_calls(
        mock_identity_store, group_users, target_groups, execute_create, execute_delete
    ):
        provision_entities_calls = []
        for i in range(len(group_users)):
            provision_entities_calls.extend(
                [
                    call(
                        mock_identity_store.create_group_membership,
                        [
                            {
                                **user,
                                "user_id": user["id"],
                                "group_id": target_groups[i]["GroupId"],
                                "log_user_name": user["primaryEmail"],
                                "log_group_name": target_groups[i]["DisplayName"],
                            }
                            for user in group_users[i][0]
                        ],
                        execute=execute_create,
                        integration_name="AWS",
                        operation_name="Creation",
                        entity_name="Group_Membership",
                        display_key="primaryEmail",
                    ),
                    call(
                        mock_identity_store.delete_group_membership,
                        [
                            {
                                **user,
                                "membership_id": user["MembershipId"],
                                "log_user_name": user["MemberId"]["UserName"],
                                "log_group_name": target_groups[i]["DisplayName"],
                            }
                            for user in group_users[i][1]
                        ],
                        execute=execute_delete,
                        integration_name="AWS",
                        operation_name="Deletion",
                        entity_name="Group_Membership",
                        display_key="MemberId.UserName",
                    ),
                ]
            )
        return provision_entities_calls

    return _provision_entities_calls


@fixture
def format_source_groups_fixture():
    def _format_source_groups(source_groups):
        # Format the source groups to match the expected patterns
        source_groups_formatted = sorted(
            (
                {
                    **group,
                    "DisplayName": group["name"].replace("AWS-", ""),
                }
                for group in source_groups
            ),
            key=lambda x: x["DisplayName"],
        )
        return source_groups_formatted

    return _format_source_groups


@fixture
def compare_list_calls_fixture():
    def _compare_list_calls(source_groups_formatted, target_groups):
        compare_list_calls = [
            call(
                {"values": source_groups_formatted, "key": "DisplayName"},
                {"values": target_groups, "key": "DisplayName"},
                mode="match",
            ),
        ]
        for i in range(len(source_groups_formatted)):
            compare_list_calls.append(
                call(
                    {
                        "values": source_groups_formatted[i]["members"],
                        "key": "primaryEmail",
                    },
                    {
                        "values": target_groups[i]["GroupMemberships"],
                        "key": "MemberId.UserName",
                    },
                    mode="sync",
                )
            )
        return compare_list_calls

    return _compare_list_calls


@fixture
def expected_output_fixture():
    def _expected_output(group_users, execute_create, execute_delete):
        expected_output = ([], [])
        for group in group_users:
            for user in group[0]:
                expected_output[0].append(
                    {
                        "entity": user["primaryEmail"],
                        "response": (
                            "membership-" + user["primaryEmail"]
                            if execute_create
                            else None
                        ),
                    }
                )
            for user in group[1]:
                expected_output[1].append(
                    {
                        "entity": user["MemberId"]["UserName"],
                        "response": True if execute_delete else False,
                    }
                )
        return expected_output

    return _expected_output


@fixture
def mock_identity_store():
    return MagicMock()


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.groups")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.sync_groups")
def test_synchronize_sync_users_and_groups_with_defaults(
    mock_sync_groups,
    mock_sync_users,
    mock_filters,
    mock_groups,
    mock_identity_store,
    mock_logger,
    google_groups_w_users,
    aws_groups_w_users,
):
    source_groups = google_groups_w_users(1, 3)
    source_users = source_groups[0]["members"]
    target_groups = aws_groups_w_users(1, 6)
    target_users_start = target_groups[0]["GroupMemberships"][:3]
    target_users_end = target_groups[0]["GroupMemberships"][3:]
    mock_groups.get_groups_from_integration.side_effect = [source_groups, target_groups]
    mock_filters.get_unique_nested_dicts.return_value = source_users
    mock_identity_store.list_users.side_effect = [
        target_users_start,
        target_users_end,
    ]
    mock_sync_users.return_value = (["users_created"], ["users_deleted"])
    mock_sync_groups.return_value = (["memberships_created"], ["memberships_deleted"])

    result = identity_center.synchronize()

    assert result == {
        "users": (["users_created"], ["users_deleted"]),
        "groups": (["memberships_created"], ["memberships_deleted"]),
    }

    assert mock_groups.get_groups_from_integration.call_count == 2
    assert mock_groups.get_groups_from_integration.call_args_list == [
        call("google_groups", query="email:aws-*", processing_filters=ANY),
        call("aws_identity_center"),
    ]

    assert mock_identity_store.list_users.call_count == 2
    logger_calls = [
        call("synchronize:Found 1 Groups and 3 Users from Source"),
        call("synchronize:Found 1 Groups and 3 Users from Target"),
        call("synchronize:Sync Completed"),
    ]
    assert mock_logger.info.call_args_list == logger_calls

    assert mock_sync_users.call_count == 1
    assert mock_sync_users.call_args_list == [
        call(source_users, target_users_start, True, False)
    ]
    assert mock_sync_groups.call_count == 1
    assert mock_sync_groups.call_args_list == [
        call(source_groups, target_groups, target_users_end, True, False)
    ]


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.sync_groups")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.groups")
def test_synchronize_sync_skip_users_if_false(
    mock_groups,
    mock_filters,
    mock_identity_store,
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
    mock_groups.get_groups_from_integration.side_effect = [
        source_groups,
        target_groups,
    ]
    mock_filters.preformat_items.return_value = source_groups
    mock_filters.get_unique_nested_dicts.return_value = source_users
    mock_identity_store.list_users.return_value = target_users
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

    assert mock_groups.get_groups_from_integration.call_count == 2

    google_groups_call = call(
        "google_groups", query="email:aws-*", processing_filters=ANY
    )
    aws_identity_center_call = call("aws_identity_center")
    assert mock_groups.get_groups_from_integration.call_args_list == [
        google_groups_call,
        aws_identity_center_call,
    ]

    assert mock_filters.get_unique_nested_dicts.call_count == 1
    assert mock_identity_store.list_users.call_count == 1
    assert mock_sync_identity_center_users.call_count == 0
    assert mock_sync_identity_center_groups.call_count == 1

    assert (
        call(source_groups, target_groups, target_users, True, False)
        in mock_sync_identity_center_groups.call_args_list
    )

    assert mock_logger.info.call_count == 3
    logger_calls = [call("synchronize:Found 3 Groups and 6 Users from Source")]
    logger_calls.append(call("synchronize:Found 3 Groups and 6 Users from Target"))
    logger_calls.append(call("synchronize:Sync Completed"))
    assert mock_logger.info.call_args_list == logger_calls


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.sync_groups")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.groups")
def test_synchronize_sync_skip_groups_false_if_false(
    mock_groups,
    mock_filters,
    mock_identity_store,
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
    mock_groups.get_groups_from_integration.side_effect = [
        source_groups,
        target_groups,
    ]
    mock_filters.preformat_items.return_value = source_groups
    mock_filters.get_unique_nested_dicts.return_value = source_users
    mock_identity_store.list_users.return_value = target_users
    mock_sync_identity_center_users.return_value = ("users_created", "users_deleted")
    mock_sync_identity_center_groups.return_value = (
        "memberships_created",
        "memberships_deleted",
    )

    response = identity_center.synchronize(enable_groups_sync=False)

    assert response == {"users": ("users_created", "users_deleted"), "groups": None}

    assert mock_groups.get_groups_from_integration.call_count == 2

    google_groups_call = call(
        "google_groups", query="email:aws-*", processing_filters=ANY
    )
    aws_identity_center_call = call("aws_identity_center")
    assert mock_groups.get_groups_from_integration.call_args_list == [
        google_groups_call,
        aws_identity_center_call,
    ]

    assert mock_filters.get_unique_nested_dicts.call_count == 1
    assert mock_identity_store.list_users.call_count == 2
    assert mock_sync_identity_center_users.call_count == 1
    assert mock_sync_identity_center_groups.call_count == 0

    assert (
        call(source_users, target_users, True, False)
        in mock_sync_identity_center_users.call_args_list
    )

    assert mock_logger.info.call_count == 3
    logger_calls = [call("synchronize:Found 3 Groups and 6 Users from Source")]
    logger_calls.append(call("synchronize:Found 3 Groups and 6 Users from Target"))
    logger_calls.append(call("synchronize:Sync Completed"))
    assert mock_logger.info.call_args_list == logger_calls


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.sync_groups")
@patch("modules.aws.identity_center.sync_users")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.groups")
def test_synchronize_sync_skip_users_and_groups_if_false(
    mock_groups,
    mock_filters,
    mock_identity_store,
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
    mock_groups.get_groups_from_integration.side_effect = [
        source_groups,
        target_groups,
    ]
    mock_filters.get_unique_nested_dicts.return_value = source_users
    mock_identity_store.list_users.return_value = target_users
    mock_sync_identity_center_users.return_value = ("users_created", "users_deleted")
    mock_sync_identity_center_groups.return_value = (
        "memberships_created",
        "memberships_deleted",
    )

    response = identity_center.synchronize(
        enable_groups_sync=False, enable_users_sync=False
    )

    assert response == {"users": None, "groups": None}

    assert mock_groups.get_groups_from_integration.call_count == 2

    google_groups_call = call(
        "google_groups", query="email:aws-*", processing_filters=ANY
    )
    aws_identity_center_call = call("aws_identity_center")
    assert mock_groups.get_groups_from_integration.call_args_list == [
        google_groups_call,
        aws_identity_center_call,
    ]

    assert mock_filters.get_unique_nested_dicts.call_count == 1
    assert mock_identity_store.list_users.call_count == 1

    assert mock_sync_identity_center_users.call_count == 0
    assert mock_sync_identity_center_groups.call_count == 0
    assert mock_logger.info.call_count == 3
    logger_calls = [call("synchronize:Found 3 Groups and 6 Users from Source")]
    logger_calls.append(call("synchronize:Found 3 Groups and 6 Users from Target"))
    logger_calls.append(call("synchronize:Sync Completed"))
    assert mock_logger.info.call_args_list == logger_calls


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
def test_sync_users_default(
    mock_filters,
    mock_entities,
    mock_identity_store,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)[:3]
    mock_filters.compare_lists.return_value = source_users, target_users
    preformat_side_effects = [
        source_users,
        source_users,
        source_users,
        source_users,
        target_users,
        target_users,
    ]
    mock_filters.preformat_items.side_effect = preformat_side_effects
    mock_entities.provision_entities.side_effect = [source_users, []]

    result = identity_center.sync_users(source_users, target_users)

    assert result == (source_users, [])

    assert (
        call(
            {"values": source_users, "key": "primaryEmail"},
            {"values": target_users, "key": "UserName"},
            mode="sync",
        )
        in mock_filters.compare_lists.call_args_list
    )
    assert (
        call(
            mock_identity_store.create_user,
            source_users,
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="User",
            display_key="primaryEmail",
        )
        in mock_entities.provision_entities.call_args_list
    )
    assert (
        call(
            mock_identity_store.delete_user,
            target_users,
            execute=False,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="User",
            display_key="UserName",
        )
    ) in mock_entities.provision_entities.call_args_list
    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
def test_sync_users_enable_delete_true(
    mock_filters,
    mock_entities,
    mock_identity_store,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)[:3]
    mock_filters.preformat_items.side_effect = [
        source_users,
        source_users,
        source_users,
        source_users,
        target_users,
        target_users,
    ]
    mock_filters.compare_lists.return_value = source_users, target_users
    mock_entities.provision_entities.side_effect = [source_users, target_users]

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
        in mock_filters.compare_lists.call_args_list
    )
    assert (
        call(
            mock_identity_store.create_user,
            source_users,
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="User",
            display_key="primaryEmail",
        )
        in mock_entities.provision_entities.call_args_list
    )
    assert (
        call(
            mock_identity_store.delete_user,
            target_users,
            execute=True,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="User",
            display_key="UserName",
        )
        in mock_entities.provision_entities.call_args_list
    )
    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 3 Users to Create and 3 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
def test_sync_users_delete_target_all_disable_delete(
    mock_filters,
    mock_entities,
    mock_identity_store,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)
    mock_filters.preformat_items.side_effect = [
        [],
        [],
        [],
        [],
        [],
        target_users,
    ]
    mock_entities.provision_entities.side_effect = [[], []]

    result = identity_center.sync_users(
        source_users, target_users, delete_target_all=True
    )

    assert result == ([], [])
    assert mock_filters.compare_lists.call_count == 0

    assert (
        call(
            mock_identity_store.create_user,
            [],
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="User",
            display_key="primaryEmail",
        )
        in mock_entities.provision_entities.call_args_list
    )
    assert (
        call(
            mock_identity_store.delete_user,
            target_users,
            execute=False,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="User",
            display_key="UserName",
        )
        in mock_entities.provision_entities.call_args_list
    )

    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 0 Users to Create and 6 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
def test_sync_users_delete_target_all_enable_delete(
    mock_filters,
    mock_entities,
    mock_identity_store,
    mock_logger,
    google_users,
    aws_users,
):
    source_users = google_users(3)
    target_users = aws_users(6)
    mock_filters.preformat_items.side_effect = [
        [],
        [],
        [],
        [],
        [],
        target_users,
    ]

    mock_entities.provision_entities.side_effect = [[], target_users]

    result = identity_center.sync_users(
        source_users,
        target_users,
        enable_user_create=True,
        enable_user_delete=True,
        delete_target_all=True,
    )

    assert result == ([], target_users)
    assert mock_filters.compare_lists.call_count == 0

    assert (
        call(
            mock_identity_store.create_user,
            [],
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="User",
            display_key="primaryEmail",
        )
        in mock_entities.provision_entities.call_args_list
    )
    assert (
        call(
            mock_identity_store.delete_user,
            target_users,
            execute=True,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="User",
            display_key="UserName",
        )
        in mock_entities.provision_entities.call_args_list
    )

    assert mock_logger.info.call_count == 1
    assert (
        call("synchronize:users:Found 0 Users to Create and 6 Users to Delete")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.identity_store")
def test_sync_groups_with_matching_groups_defaults(
    mock_identity_store,
    mock_entities,
    mock_filters,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
    provision_entities_side_effect_fixture,
    provision_entities_calls_fixture,
    format_source_groups_fixture,
    compare_list_calls_fixture,
    expected_output_fixture,
):
    # source groups get formatted to match the expected patterns
    source_groups = google_groups_w_users(3, 3, group_prefix="AWS-")
    source_groups_formatted = format_source_groups_fixture(source_groups)
    mock_filters.preformat_items.return_value = source_groups_formatted

    target_groups = aws_groups_w_users(3, 6)
    target_groups.sort(key=lambda x: x["DisplayName"])

    # first time compare list is called returns formatted source groups and target groups
    compare_list_side_effects = [(source_groups_formatted, target_groups)]
    group_users = []
    for i in range(len(source_groups_formatted)):
        compare_list_side_effects.append(
            (
                source_groups_formatted[i]["members"],
                target_groups[i]["GroupMemberships"][3:],
            )
        )
        group_users.append(
            (
                source_groups_formatted[i]["members"],
                target_groups[i]["GroupMemberships"][3:],
            )
        )
    # 3 other times its called it will be the group's users
    mock_filters.compare_lists.side_effect = compare_list_side_effects

    # target users are used to resolve the users from the target system
    target_users = aws_users(6)

    mock_entities.provision_entities.side_effect = (
        provision_entities_side_effect_fixture
    )

    mock_filters.compare_lists.side_effect = compare_list_side_effects

    result = identity_center.sync_groups(source_groups, target_groups, target_users)

    expected_output = expected_output_fixture(group_users, True, False)
    assert result == expected_output

    assert mock_filters.compare_lists.call_count == 4
    compare_list_calls = compare_list_calls_fixture(
        source_groups_formatted, target_groups
    )
    assert compare_list_calls == mock_filters.compare_lists.call_args_list

    assert mock_entities.provision_entities.call_count == 6

    provision_entities_calls = provision_entities_calls_fixture(
        mock_identity_store, group_users, target_groups, True, False
    )

    assert provision_entities_calls == mock_entities.provision_entities.call_args_list


@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.identity_store")
def test_sync_groups_with_matching_groups_delete_enable(
    mock_identity_store,
    mock_entities,
    mock_filters,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
    provision_entities_side_effect_fixture,
    provision_entities_calls_fixture,
    format_source_groups_fixture,
    compare_list_calls_fixture,
    expected_output_fixture,
):
    # source groups get formatted to match the expected patterns
    source_groups = google_groups_w_users(3, 3, group_prefix="AWS-")
    source_groups_formatted = format_source_groups_fixture(source_groups)
    mock_filters.preformat_items.return_value = source_groups_formatted

    target_groups = aws_groups_w_users(3, 6)
    target_groups.sort(key=lambda x: x["DisplayName"])

    # first time compare list is called returns formatted source groups and target groups
    compare_list_side_effects = [(source_groups_formatted, target_groups)]
    group_users = []
    for i in range(len(source_groups_formatted)):
        compare_list_side_effects.append(
            (
                source_groups_formatted[i]["members"],
                target_groups[i]["GroupMemberships"][3:],
            )
        )
        group_users.append(
            (
                source_groups_formatted[i]["members"],
                target_groups[i]["GroupMemberships"][3:],
            )
        )
    # 3 other times its called it will be the group's users
    mock_filters.compare_lists.side_effect = compare_list_side_effects

    # target users are used to resolve the users from the target system
    target_users = aws_users(6)

    mock_entities.provision_entities.side_effect = (
        provision_entities_side_effect_fixture
    )

    mock_filters.compare_lists.side_effect = compare_list_side_effects

    result = identity_center.sync_groups(
        source_groups, target_groups, target_users, enable_membership_delete=True
    )

    expected_output = expected_output_fixture(group_users, True, True)
    assert result == expected_output

    assert mock_filters.compare_lists.call_count == 4
    compare_list_calls = compare_list_calls_fixture(
        source_groups_formatted, target_groups
    )
    assert compare_list_calls == mock_filters.compare_lists.call_args_list

    assert mock_entities.provision_entities.call_count == 6

    provision_entities_calls = provision_entities_calls_fixture(
        mock_identity_store, group_users, target_groups, True, True
    )

    assert provision_entities_calls == mock_entities.provision_entities.call_args_list


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.identity_store")
def test_sync_groups_empty_source_groups(
    mock_identity_store,
    mock_filters,
    mock_logger,
    aws_groups_w_users,
    aws_users,
):
    source_groups = []
    target_groups = aws_groups_w_users(3, 3, group_prefix="target-")
    target_users = aws_users(3)
    mock_filters.preformat_items.return_value = []
    mock_filters.compare_lists.return_value = [], []

    result = identity_center.sync_groups(
        source_groups, target_groups, target_users, enable_membership_delete=True
    )

    assert result == ([], [])
    assert (
        call(
            {"values": source_groups, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_filters.compare_lists.call_args_list
    )
    assert mock_filters.compare_lists.call_count == 1
    assert mock_identity_store.create_group_membership.call_count == 0
    assert mock_identity_store.delete_group_membership.call_count == 0
    assert mock_logger.info.call_count == 2
    assert (
        call("synchronize:groups:Found 0 Source Groups and 0 Target Groups")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.identity_store")
def test_sync_groups_empty_target_groups(
    mock_identity_store,
    mock_filters,
    mock_logger,
    aws_users,
    google_groups_w_users,
):
    source_groups = google_groups_w_users(3, 3, group_prefix="source-")
    source_groups_formatted = [
        {
            **group,
            "DisplayName": group["name"],
        }
        for group in source_groups
    ]
    target_groups = []
    target_users = aws_users(3)
    mock_filters.preformat_items.return_value = source_groups_formatted
    mock_filters.compare_lists.return_value = [], []

    result = identity_center.sync_groups(
        source_groups_formatted,
        target_groups,
        target_users,
        enable_membership_delete=True,
    )

    assert result == ([], [])
    assert (
        call(
            {"values": source_groups_formatted, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_filters.compare_lists.call_args_list
    )
    assert mock_filters.compare_lists.call_count == 1
    assert mock_identity_store.create_group_membership.call_count == 0
    assert mock_identity_store.delete_group_membership.call_count == 0
    assert mock_logger.info.call_count == 2
    assert (
        call("synchronize:groups:Found 0 Source Groups and 0 Target Groups")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.logger")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.identity_store")
def test_sync_groups_without_matching_groups_to_sync(
    mock_identity_store,
    mock_filters,
    mock_logger,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
):
    source_groups = google_groups_w_users(3, 3, group_prefix="source-")
    source_groups_formatted = [
        {
            **group,
            "DisplayName": group["name"],
        }
        for group in source_groups
    ]
    target_groups = aws_groups_w_users(3, 3, group_prefix="target-")
    target_users = aws_users(3)
    mock_filters.preformat_items.return_value = source_groups_formatted
    mock_filters.compare_lists.return_value = [], []

    result = identity_center.sync_groups(
        source_groups_formatted,
        target_groups,
        target_users,
        enable_membership_delete=True,
    )

    assert result == ([], [])
    assert (
        call(
            {"values": source_groups_formatted, "key": "DisplayName"},
            {"values": target_groups, "key": "DisplayName"},
            mode="match",
        )
        in mock_filters.compare_lists.call_args_list
    )
    assert mock_filters.compare_lists.call_count == 1
    assert mock_identity_store.create_group_membership.call_count == 0
    assert mock_identity_store.delete_group_membership.call_count == 0
    assert mock_logger.info.call_count == 2
    assert (
        call("synchronize:groups:Found 0 Source Groups and 0 Target Groups")
        in mock_logger.info.call_args_list
    )


@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.users")
def test_provision_aws_user_create(
    mock_users,
    mock_filters,
    mock_entities,
    mock_identity_store,
    google_users,
):
    source_users = google_users(3)
    users_emails = ["user-email1@test.com"]
    mock_users.get_users_from_integration.return_value = source_users
    mock_filters.preformat_items.return_value = [source_users[0]]
    mock_entities.provision_entities.return_value = [
        {
            "entity": source_users[0]["primaryEmail"],
            "response": users_emails[0],
        }
    ]
    identity_center.provision_aws_users("create", users_emails)
    mock_users.get_users_from_integration.assert_called_once_with("google_directory")
    mock_filters.preformat_items.call_count == 4
    mock_entities.provision_entities.assert_called_once_with(
        mock_identity_store.create_user,
        [source_users[0]],
        execute=True,
        integration_name="AWS",
        operation_name="Creation",
        entity_name="User",
        display_key="primaryEmail",
    )


@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.users")
def test_provision_aws_user_create_missing_users(
    mock_users,
    mock_filters,
    mock_entities,
    mock_identity_store,
    google_users,
):
    source_users = google_users(3)
    users_emails = ["user-email4@test.com"]
    mock_users.get_users_from_integration.return_value = source_users
    identity_center.provision_aws_users("create", users_emails)
    mock_users.get_users_from_integration.assert_called_once_with("google_directory")
    mock_filters.preformat_items.call_count == 0
    mock_entities.provision_entities.assert_not_called
    mock_identity_store.create_user.assert_not_called


@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.users")
def test_provision_aws_user_delete(
    mock_users,
    mock_filters,
    mock_entities,
    mock_identity_store,
    aws_users
):
    target_users = aws_users(6)
    users_emails = ["user-email1@test.com"]
    mock_users.get_users_from_integration.return_value = target_users
    mock_filters.preformat_items.return_value = [target_users[0]]
    mock_entities.provision_entities.return_value = [
        {
            "entity": target_users[0]["UserName"],
            "response": users_emails[0],
        }
    ]
    identity_center.provision_aws_users("delete", users_emails)
    mock_users.get_users_from_integration.assert_called_once_with("aws_identity_center")
    mock_filters.preformat_items.call_count == 2
    mock_entities.provision_entities.assert_called_once_with(
        mock_identity_store.delete_user,
        [target_users[0]],
        execute=True,
        integration_name="AWS",
        operation_name="Deletion",
        entity_name="User",
        display_key="UserName",
    )


@patch("modules.aws.identity_center.identity_store")
@patch("modules.aws.identity_center.entities")
@patch("modules.aws.identity_center.filters")
@patch("modules.aws.identity_center.users")
def test_provision_aws_user_delete_missing_users(
    mock_users, mock_filters, mock_entities, mock_identity_store, aws_users
):
    target_users = aws_users(3)
    users_emails = ["user-email4@test.com"]
    mock_users.get_users_from_integration.return_value = target_users
    identity_center.provision_aws_users("delete", users_emails)
    mock_users.get_users_from_integration.assert_called_once_with("aws_identity_center")
    mock_filters.preformat_items.call_count == 0
    mock_entities.provision_entities.assert_not_called
    mock_identity_store.create_user.assert_not_called


def test_provision_aws_user_invalid_operation():
    with raises(ValueError):
        identity_center.provision_aws_users("invalid-operation", ["user.email1@test.com"])
