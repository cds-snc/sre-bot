import json
from unittest.mock import patch, call, ANY, MagicMock
from pytest import fixture

from modules.aws import identity_center


@fixture
def provision_entities_side_effect(mock_identity_store):
    def _provision_entities_side_effect(function, entities, **kwargs):
        entities_provisioned = []
        function_name = function._mock_name.split(".")[-1]

        for entity in entities:
            if function_name == "create_user":
                entities_provisioned.append(
                    {
                        "entity": entity["primaryEmail"],
                        "response": entity["primaryEmail"],
                    }
                )
            elif function_name == "delete_user":
                entities_provisioned.append(
                    {"entity": entity["UserName"], "response": True}
                )
            elif function_name == "create_group_membership":
                entities_provisioned.append(
                    {
                        "entity": entity["primaryEmail"],
                        "response": "membership-" + entity["primaryEmail"],
                    }
                )
            elif function_name == "delete_group_membership":
                entities_provisioned.append(
                    {"entity": entity["MemberId"]["UserName"], "response": True}
                )
        return entities_provisioned

    return _provision_entities_side_effect


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

    assert mock_logger.info.call_count == 2
    logger_calls = [call("synchronize:Found 3 Groups and 6 Users from Source")]
    logger_calls.append(call("synchronize:Found 3 Groups and 6 Users from Target"))
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

    assert mock_logger.info.call_count == 2
    logger_calls = [call("synchronize:Found 3 Groups and 6 Users from Source")]
    logger_calls.append(call("synchronize:Found 3 Groups and 6 Users from Target"))
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
    assert mock_logger.info.call_count == 2
    logger_calls = [call("synchronize:Found 3 Groups and 6 Users from Source")]
    logger_calls.append(call("synchronize:Found 3 Groups and 6 Users from Target"))
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
def test_sync_groups_defaults_with_matching_groups(
    mock_identity_store,
    mock_entities,
    mock_filters,
    aws_groups_w_users,
    aws_users,
    google_groups_w_users,
    provision_entities_side_effect,
):
    # source groups get formatted to match the expected patterns
    source_groups = google_groups_w_users(3, 3, group_prefix="AWS-")
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
    mock_filters.preformat_items.return_value = source_groups_formatted
    target_groups = aws_groups_w_users(3, 6)
    target_groups.sort(key=lambda x: x["DisplayName"])

    # first time compare list is called returns formatted source groups and target groups
    compare_list_side_effects = [
        (source_groups_formatted, target_groups),
    ]
    for i in range(len(source_groups_formatted)):
        compare_list_side_effects.append(
            source_groups_formatted[i]["members"]
        )
        compare_list_side_effects.append(
            target_groups[i]["GroupMemberships"]
        )
    group_users = [(source_groups_formatted[i]["members"], target_groups[i]["GroupMemberships"][3:]) for i in range(3)]

    target_users = aws_users(6)
    target_users_to_remove = [
        user for group in target_groups for user in group["GroupMemberships"][3:]
    ]
    source_users_to_create = [
        user for source_group in source_groups for user in source_group["members"]
    ]

    mock_filters.compare_lists.side_effect = [(source_groups_formatted, target_groups)] + group_users
    
    formatted_group_users = [
        (
            [
                {**user, "user_id": user["id"], "group_id": target_groups[i]["GroupId"]}
                for user in group_users[i][0]
            ],
            [
                {**user, "user_id": user["MembershipId"], "group_id": target_groups[i]["GroupId"]}
                for user in group_users[i][1]
            ],
        )
        for i in range(3)
    ]

    formatted_target_users = [
        {**user, "membership_id": user["MembershipId"]}
        for user in target_users_to_remove
        if user.get("MembershipId")
    ]
    mock_entities.provision_entities.side_effect = provision_entities_side_effect

    expected_output = ([], [])
    for user in source_users_to_create:
        expected_output[0].append(
            {
                "entity": user["primaryEmail"],
                "response": "membership-" + user["primaryEmail"],
            }
        )
    for user in formatted_target_users:
        expected_output[1].append(
            {"entity": user["MemberId"]["UserName"], "response": True}
        )

    result = identity_center.sync_groups(source_groups, target_groups, target_users)

    assert result == expected_output

    assert mock_filters.compare_lists.call_count == 4
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

    assert compare_list_calls == mock_filters.compare_lists.call_args_list
    assert mock_entities.provision_entities.call_count == 6
    provision_entities_calls = [
        call(
            mock_identity_store.create_group_membership,
            formatted_group_users[0][0],
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="Group_Membership",
            display_key="primaryEmail",
        ),
        call(
            mock_identity_store.delete_group_membership,
            formatted_target_users[:3],
            execute=False,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="Group_Membership",
            display_key="MemberId.UserName",
        ),
        call(
            mock_identity_store.create_group_membership,
            formatted_group_users[1][0],
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="Group_Membership",
            display_key="primaryEmail",
        ),
        call(
            mock_identity_store.delete_group_membership,
            formatted_target_users[3:6],
            execute=False,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="Group_Membership",
            display_key="MemberId.UserName",
        ),
        call(
            mock_identity_store.create_group_membership,
            formatted_group_users[2][0],
            execute=True,
            integration_name="AWS",
            operation_name="Creation",
            entity_name="Group_Membership",
            display_key="primaryEmail",
        ),
        call(
            mock_identity_store.delete_group_membership,
            formatted_target_users[6:],
            execute=False,
            integration_name="AWS",
            operation_name="Deletion",
            entity_name="Group_Membership",
            display_key="MemberId.UserName",
        ),
    ]

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


# @patch("modules.aws.identity_center.DRY_RUN", False)
# @patch("modules.aws.identity_center.logger")
# @patch("modules.provisioning.entities.logger")
# @patch("modules.aws.identity_center.identity_store")
# @patch("modules.aws.identity_center.identity_store")
# @patch("modules.aws.identity_center.groups")
# def test_synchronize_enable_all(
#     mock_groups,
#     mock_identity_store,
#     mock_identity_store,
#     mock_entities.provision_entities_logger,
#     mock_logger,
#     google_groups_w_users,
#     google_users,
#     aws_groups_w_users,
#     aws_users,
# ):
#     # Setup source and target users for test
#     source_users = google_users(9)[:6]
#     target_users = aws_users(9)
#     # keep last 6 users for the first return value
#     # keep first 6 users for the second return value
#     mock_identity_store.list_users.side_effect = [target_users[3:], target_users[:6]]

#     # Setup source and target users for expected output
#     def create_user_side_effect(email, first_name, family_name, **kwargs):
#         return email

#     def delete_user_side_effect(user_id, **kwargs):
#         return kwargs["UserName"]

#     mock_identity_store.create_user.side_effect = create_user_side_effect
#     mock_identity_store.delete_user.side_effect = delete_user_side_effect

#     expected_target_users_created = []
#     for user in source_users[:3]:
#         expected_target_users_created.append(
#             {"entity": user, "response": user["primaryEmail"]}
#         )
#         user["email"] = user["primaryEmail"]
#         user["first_name"] = user["name"]["givenName"]
#         user["family_name"] = user["name"]["familyName"]

#     deleted_target_users = target_users[6:]
#     expected_target_users_deleted = []
#     for user in deleted_target_users:
#         expected_target_users_deleted.append(
#             {"entity": user, "response": user["UserName"]}
#         )

#     # 3 groups, with 9 users in each group
#     source_groups = google_groups_w_users(3, 9, group_prefix="AWS-")
#     # only keep first 6 users in groups
#     for group in source_groups:
#         group["members"] = group["members"][:6]

#     # 3 groups, with 9 users in each group
#     target_groups = aws_groups_w_users(3, 9)
#     # only keep last 6 users in groups
#     for group in target_groups:
#         group["GroupMemberships"] = group["GroupMemberships"][3:]

#     # Setup source and target groups for expected output
#     mock_groups.get_groups_from_integration.side_effect = [
#         source_groups,
#         target_groups,
#     ]

#     # expected_group_memberships_to_create = [
#     #     {"entity": group, "response": group["MembershipId"]}
#     #     for group in target_groups["GroupMemberships"]
#     # ]

#     expected_group_memberships_to_create = [
#         {"entity": {"email": "user-email1@test.com"}, "response": "aws-group_id1"},
#         {"entity": {"email": "user-email2@test.com"}, "response": "aws-group_id2"},
#         {"entity": {"email": "user-email3@test.com"}, "response": "aws-group_id3"},
#         {"entity": {"email": "user-email1@test.com"}, "response": "aws-group_id1"},
#         {"entity": {"email": "user-email2@test.com"}, "response": "aws-group_id2"},
#         {"entity": {"email": "user-email3@test.com"}, "response": "aws-group_id3"},
#         {"entity": {"email": "user-email1@test.com"}, "response": "aws-group_id1"},
#         {"entity": {"email": "user-email2@test.com"}, "response": "aws-group_id2"},
#         {"entity": {"email": "user-email3@test.com"}, "response": "aws-group_id3"},
#     ]

#     expected_group_memberships_to_delete = [
#         {"entity": {"email": "user-email7@test.com"}, "response": True},
#         {"entity": {"email": "user-email8@test.com"}, "response": True},
#         {"entity": {"email": "user-email9@test.com"}, "response": True},
#         {"entity": {"email": "user-email7@test.com"}, "response": True},
#         {"entity": {"email": "user-email8@test.com"}, "response": True},
#         {"entity": {"email": "user-email9@test.com"}, "response": True},
#         {"entity": {"email": "user-email7@test.com"}, "response": True},
#         {"entity": {"email": "user-email8@test.com"}, "response": True},
#         {"entity": {"email": "user-email9@test.com"}, "response": True},
#     ]

#     def create_membership_side_effect(group_id, user_id, **kwargs):
#         return group_id

#     def delete_membership_side_effect(membership_id, **kwargs):
#         return True

#     mock_identity_store.create_group_membership.side_effect = create_membership_side_effect
#     mock_identity_store.delete_group_membership.side_effect = delete_membership_side_effect

#     result = identity_center.synchronize(
#         enable_users_sync=True,
#         enable_groups_sync=True,
#         enable_user_delete=True,
#         enable_membership_delete=True,
#     )

#     assert result["groups"][0] == expected_group_memberships_to_create
#     # assert result == {
#     #     "users": (expected_target_users_created, expected_target_users_deleted),
#     #     "groups": (
#     #         expected_group_memberships_to_create,
#     #         expected_group_memberships_to_delete,
#     #     ),
#     # }

#     assert mock_logger.info.call_count == 28
#     assert mock_entities.provision_entities_logger.info.call_count == 0
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

#     assert (
#         call("aws:Starting creation of 3 user(s)")
#     ) in mock_entities.provision_entities_logger.info.call_args_list

#     for user in expected_target_users_created:
#         assert (
#             call(f"aws:Successful creation of user(s) {user['entity']['primaryEmail']}")
#             in mock_entities.provision_entities_logger.info.call_args_list
#         )
#     for user in expected_target_users_deleted:
#         assert (
#             call(f"aws:Successful deletion of user(s) {user['entity']['UserName']}")
#             in mock_entities.provision_entities_logger.info.call_args_list
#         )
#     for group in target_groups:
#         for user in expected_group_memberships_to_create:
#             assert (
#                 call(
#                     f"create_group_memberships:Successfully added user {user} to group {group['DisplayName']}"
#                 )
#                 in mock_logger.info.call_args_list
#             )

#     for group in target_groups:
#         for user in expected_group_memberships_to_delete:
#             assert (
#                 call(
#                     f"delete_group_memberships:Successfully removed user {user} from group {group['DisplayName']}"
#                 )
#                 in mock_logger.info.call_args_list
#             )

#     assert mock_identity_store.create_user.call_count == 3
#     assert mock_identity_store.delete_user.call_count == 3
#     assert mock_identity_store.create_group_membership.call_count == 9
#     assert mock_identity_store.delete_group_membership.call_count == 9


# @patch("modules.aws.identity_center.DRY_RUN", True)
# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.identity_store")
#
# @patch("modules.aws.identity_center.identity_store")
# @patch("modules.aws.identity_center.groups")
# def test_synchronize_defaults_dry_run_true(
#     mock_groups,
#     mock_identity_store,
#
#     mock_identity_store,
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

#     mock_groups.get_groups_from_integration.side_effect = [
#         source_groups,
#         target_groups,
#     ]

#     # keep last 6 users
#     target_users = aws_users(9)
#     mock_identity_store.list_users.side_effect = [target_users[3:], target_users]

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

#     assert mock_identity_store.create_user.call_count == 0
#     assert mock_identity_store.delete_user.call_count == 0
#     assert mock_identity_store.create_group_membership.call_count == 0
#     assert mock_identity_store.delete_group_membership.call_count == 0


# @patch("modules.aws.identity_center.DRY_RUN", False)
# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.identity_store")
#
# @patch("modules.aws.identity_center.identity_store")
# @patch("modules.aws.identity_center.groups")
# def test_synchronize_enable_delete_dry_run_false(
#     mock_groups,
#     mock_identity_store,
#
#     mock_identity_store,
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

#     mock_groups.get_groups_from_integration.side_effect = [
#         source_groups,
#         target_groups,
#     ]

#     # keep last 6 users
#     target_users = aws_users(9)
#     mock_identity_store.list_users.side_effect = [target_users[3:], target_users]
#     mock_identity_store.create_user.side_effect = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]
#     mock_identity_store.create_group_membership.side_effect = [
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
#     mock_identity_store.delete_group_membership.side_effect = [
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

#     assert mock_identity_store.create_user.call_count == 3
#     assert mock_identity_store.delete_user.call_count == 3
#     assert mock_identity_store.create_group_membership.call_count == 9
#     assert mock_identity_store.delete_group_membership.call_count == 9


# @patch("modules.aws.identity_center.DRY_RUN", True)
# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.identity_store")
#
# @patch("modules.aws.identity_center.identity_store")
# @patch("modules.aws.identity_center.groups")
# def test_synchronize_enable_delete_dry_run_true(
#     mock_groups,
#     mock_identity_store,
#
#     mock_identity_store,
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

#     mock_groups.get_groups_from_integration.side_effect = [
#         source_groups,
#         target_groups,
#     ]

#     # keep last 6 users
#     target_users = aws_users(9)
#     mock_identity_store.list_users.side_effect = [target_users[3:], target_users]
#     mock_identity_store.create_user.side_effect = [
#         "user-email1@test.com",
#         "user-email2@test.com",
#         "user-email3@test.com",
#     ]
#     mock_identity_store.create_group_membership.side_effect = [
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
#     mock_identity_store.delete_group_membership.side_effect = [
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

#     assert mock_identity_store.create_user.call_count == 0
#     assert mock_identity_store.delete_user.call_count == 0
#     assert mock_identity_store.create_group_membership.call_count == 0
#     assert mock_identity_store.delete_group_membership.call_count == 0


# @patch("modules.aws.identity_center.filters")
# @patch("modules.aws.identity_center.entities")
# @patch("modules.aws.identity_center.identity_store")
# def test_sync_groups_defaults_with_matching_groups(
#     mock_identity_store, mock_entities, mock_filters
# ):
#     mock_filters.preformat_items.return_value = [
#         {"name": "group1", "DisplayName": "group1"}
#     ]
#     mock_filters.compare_lists.side_effect = [
#         (
#             [{"name": "group1", "DisplayName": "group1"}],
#             [{"name": "group1", "DisplayName": "group1"}],
#         ),
#         ([{"primaryEmail": "user1"}], [{"MembershipId": "user1"}]),
#     ]
#     mock_entities.provision_entities.side_effect = [
#         [{"user_id": "user1", "group_id": "group1"}],
#         [{"membership_id": "user1"}],
#     ]
#     created, deleted = identity_center.sync_groups(
#         [{"name": "group1"}], [{"name": "group1"}], [{"UserName": "user1"}]
#     )
#     assert created == [{"user_id": "user1", "group_id": "group1"}]
#     assert deleted == [{"membership_id": "user1"}]


# @patch("modules.aws.identity_center.filters")
# @patch("modules.aws.identity_center.entities")
# @patch("modules.aws.identity_center.identity_store")
# def test_sync_groups_empty_source(mock_identity_store, mock_entities, mock_filters):
#     created, deleted = identity_center.sync_groups(
#         [], [{"name": "group1"}], [{"UserName": "user1"}]
#     )
#     assert created == []
#     assert deleted == []


# @patch("modules.aws.identity_center.filters")
# @patch("modules.aws.identity_center.entities")
# @patch("modules.aws.identity_center.identity_store")
# def test_sync_groups_empty_target(mock_identity_store, mock_entities, mock_filters):
#     created, deleted = identity_center.sync_groups(
#         [{"name": "group1"}], [], [{"UserName": "user1"}]
#     )
#     assert created == []
#     assert deleted == []


# @patch("modules.aws.identity_center.filters")
# @patch("modules.aws.identity_center.entities")
# @patch("modules.aws.identity_center.identity_store")
# def test_sync_groups_non_matching_groups(
#     mock_identity_store, mock_entities, mock_filters
# ):
#     mock_filters.preformat_items.return_value = [
#         {"name": "group1", "DisplayName": "group1"}
#     ]
#     mock_filters.compare_lists.return_value = ([], [])
#     created, deleted = identity_center.sync_groups(
#         [{"name": "group1"}], [{"name": "group2"}], [{"UserName": "user1"}]
#     )
#     assert created == []
#     assert deleted == []


# @patch("modules.aws.identity_center.filters")
# @patch("modules.aws.identity_center.entities")
# @patch("modules.aws.identity_center.identity_store")
# def test_sync_groups_users_to_add_and_remove_not_found(
#     mock_identity_store, mock_entities, mock_filters
# ):
#     mock_filters.preformat_items.return_value = [
#         {"name": "group1", "DisplayName": "group1"}
#     ]
#     mock_filters.compare_lists.side_effect = [
#         (
#             [{"name": "group1", "DisplayName": "group1"}],
#             [{"name": "group1", "DisplayName": "group1"}],
#         ),
#         ([], []),
#     ]
#     created, deleted = identity_center.sync_groups(
#         [{"name": "group1"}], [{"name": "group1"}], [{"UserName": "user1"}]
#     )
#     assert created == []
#     assert deleted == []


# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.filters.preformat_items")
# @patch("modules.aws.identity_center.filters")
# @patch("modules.aws.identity_center.identity_store")
#
# @patch("modules.aws.identity_center.entities")
# def test_sync_groups_defaults(
#     mock_entities,
#
#     mock_identity_store,
#     mock_filters,
#     mock_filters,
#     mock_logger,
#     aws_groups_w_users,
#     aws_users,
#     google_groups_w_users,
#     google_users,
# ):
#     # defaults will create memberships and not delete any
#     source_groups = google_groups_w_users(1, 6, group_prefix="AWS-")
#     preformated_source_groups = google_groups_w_users(1, 6)
#     target_groups = aws_groups_w_users(1, 6)
#     target_users = aws_users(6)

#     mock_filters.preformat_items.return_value = preformated_source_groups
#     # Mock the behavior of compare_lists to return the source and target groups
#     mock_filters.compare_lists.return_value = (preformated_source_groups, target_groups)

#     def create_user_side_effect(email, first_name, family_name, **kwargs):
#         return email

#     def delete_user_side_effect(user_id, **kwargs):
#         return kwargs["UserName"]

#     def create_membership_side_effect(email, first_name, family_name, **kwargs):
#         return email

#     def delete_membership_side_effect(user_id, **kwargs):
#         return kwargs["UserName"]

#     # Mock the behavior of create_group_membership to return a membership id
#     mock_identity_store.create_group_membership.return_value = {
#         "entity": "group_membership",
#         "response": "membership_id_1",
#     }

#     # Mock the behavior of delete_group_membership to return False
#     mock_identity_store.delete_group_membership.return_value = False

#     # Call the function under test
#     result = identity_center.sync_groups(source_groups, target_groups, target_users)

#     # Assert that the function behaved as expected
#     assert result == (
#         [
#             {"entity": "group_membership", "response": "membership_id_1"},
#             {"entity": "group_membership", "response": "membership_id_1"},
#             {"entity": "group_membership", "response": "membership_id_1"},
#         ],
#         [False, False, False],
#     )


# @patch("modules.aws.identity_center.logger")
# @patch("modules.aws.identity_center.filters")
# @patch("modules.aws.identity_center.identity_store")
# def test_sync_groups_enable_delete_true(
#
#     mock_identity_store,
#     mock_filters,
#     mock_logger,
#     aws_groups_w_users,
#     aws_users,
#     google_groups_w_users,
# ):
#     source_groups = google_groups_w_users(3, 6, group_prefix="AWS-")
#     for group in source_groups:
#         group["members"] = group["members"][:3]
#         group["DisplayName"] = group["name"]
#     target_groups = aws_groups_w_users(3, 6, group_prefix="target-")
#     for group in target_groups:
#         group["GroupMemberships"] = group["GroupMemberships"][3:]
#     target_users = aws_users(6)

#     side_effects = [
#         (source_groups, target_groups),
#         (source_groups[0]["members"], target_groups[0]["GroupMemberships"]),
#         (source_groups[1]["members"], target_groups[1]["GroupMemberships"]),
#         (source_groups[2]["members"], target_groups[2]["GroupMemberships"]),
#     ]
#     mock_filters.compare_lists.side_effect = side_effects
#     mock_identity_store.create_group_membership.side_effect = [
#         ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
#         ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
#         ["target-membership_id_1", "target-membership_id_2", "target-membership_id_3"],
#     ]
#     mock_identity_store.delete_group_membership.side_effect = [
#         ["target-membership_id_4", "target-membership_id_5", "target-membership_id_6"],
#         ["target-membership_id_4", "target-membership_id_5", "target-membership_id_6"],
#         ["target-membership_id_4", "target-membership_id_5", "target-membership_id_6"],
#     ]
#     result = identity_center.sync_groups(
#         source_groups, target_groups, target_users, enable_membership_delete=True
#     )

#     assert result == (
#         [
#             "target-membership_id_1",
#             "target-membership_id_2",
#             "target-membership_id_3",
#             "target-membership_id_1",
#             "target-membership_id_2",
#             "target-membership_id_3",
#             "target-membership_id_1",
#             "target-membership_id_2",
#             "target-membership_id_3",
#         ],
#         [
#             "target-membership_id_4",
#             "target-membership_id_5",
#             "target-membership_id_6",
#             "target-membership_id_4",
#             "target-membership_id_5",
#             "target-membership_id_6",
#             "target-membership_id_4",
#             "target-membership_id_5",
#             "target-membership_id_6",
#         ],
#     )
#     assert (
#         call(
#             {"values": source_groups, "key": "DisplayName"},
#             {"values": target_groups, "key": "DisplayName"},
#             mode="match",
#         )
#         in mock_filters.compare_lists.call_args_list
#     )
#     assert mock_filters.compare_lists.call_count == 4
#     assert mock_identity_store.create_group_membership.call_count == 3
#     assert mock_identity_store.delete_group_membership.call_count == 3
#     assert mock_logger.info.call_count == 5
#     assert (
#         call("synchronize:groups:Found 3 Source Groups and 3 Target Groups")
#         in mock_logger.info.call_args_list
#     )
