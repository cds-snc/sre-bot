import os
from unittest.mock import call, patch  # type: ignore
from integrations.aws import identity_store


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_users(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["User1", "User2"]

    # Call the function with no arguments
    result = identity_store.list_users()

    # Check that execute_aws_api_call was called with the correct arguments
    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_users",
        paginated=True,
        keys=["Users"],
        IdentityStoreId="test_instance_id",
    )

    # Check that the function returned the correct result
    assert result == ["User1", "User2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_users_with_identity_store_id(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["User1", "User2"]

    result = identity_store.list_users(IdentityStoreId="custom_instance_id")

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_users",
        paginated=True,
        keys=["Users"],
        IdentityStoreId="custom_instance_id",
    )
    assert result == ["User1", "User2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_users_with_kwargs(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["User1", "User2"]

    result = identity_store.list_users(custom_param="custom_value")

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_users",
        paginated=True,
        keys=["Users"],
        IdentityStoreId="test_instance_id",
        custom_param="custom_value",
    )
    assert result == ["User1", "User2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_groups(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["Group1", "Group2"]

    result = identity_store.list_groups()

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_groups",
        paginated=True,
        keys=["Groups"],
    )

    assert result == ["Group1", "Group2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_groups_custom_identity_store_id(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["Group1", "Group2"]

    result = identity_store.list_groups(IdentityStoreId="custom_instance_id")

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_groups",
        paginated=True,
        keys=["Groups"],
        IdentityStoreId="custom_instance_id",
    )

    assert result == ["Group1", "Group2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_groups_with_kwargs(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["Group1", "Group2"]

    result = identity_store.list_groups(
        IdentityStoreId="custom_instance_id", extra_arg="extra_value"
    )

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_groups",
        paginated=True,
        keys=["Groups"],
        IdentityStoreId="custom_instance_id",
        extra_arg="extra_value",
    )

    assert result == ["Group1", "Group2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_group_memberships(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["Membership1", "Membership2"]

    result = identity_store.list_group_memberships("test_group_id")

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_group_memberships",
        ["GroupMemberships"],
        GroupId="test_group_id",
    )

    assert result == ["Membership1", "Membership2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.list_group_memberships")
def test_list_groups_with_membership(
    mock_list_group_memberships, mock_execute_aws_api_call
):
    mock_execute_aws_api_call.return_value = [
        {"GroupId": "Group1"},
        {"GroupId": "Group2"},
    ]
    mock_list_group_memberships.side_effect = [["Membership1"], ["Membership2"]]

    result = identity_store.list_groups_with_membership()

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_groups",
        paginated=True,
        keys=["Groups"],
    )

    mock_list_group_memberships.assert_has_calls(
        [
            call("Group1"),
            call("Group2"),
        ]
    )

    assert result == [
        {"GroupId": "Group1", "GroupMemberships": ["Membership1"]},
        {"GroupId": "Group2", "GroupMemberships": ["Membership2"]},
    ]
