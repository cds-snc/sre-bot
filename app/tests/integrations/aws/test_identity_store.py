import os
from unittest.mock import call, patch  # type: ignore
import pytest
from integrations.aws import identity_store


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
def test_resolve_identity_store_id():
    assert identity_store.resolve_identity_store_id({}) == {
        "IdentityStoreId": "test_instance_id"
    }
    assert identity_store.resolve_identity_store_id(
        {"identity_store_id": "test_id"}
    ) == {"IdentityStoreId": "test_id"}
    assert identity_store.resolve_identity_store_id({"IdentityStoreId": "test_id"}) == {
        "IdentityStoreId": "test_id"
    }


@patch.dict(os.environ, clear=True)
def test_resolve_identity_store_id_no_env():
    with pytest.raises(ValueError):
        identity_store.resolve_identity_store_id({})


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_create_user(mock_resolve_identity_store_id, mock_execute_aws_api_call):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = {"UserId": "test_user_id"}
    email = "test@example.com"
    first_name = "Test"
    family_name = "User"

    # Act
    result = identity_store.create_user(email, first_name, family_name)

    # Assert
    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "create_user",
        IdentityStoreId="test_instance_id",
        UserName=email,
        Emails=[{"Value": email, "Type": "WORK", "Primary": True}],
        Name={"GivenName": first_name, "FamilyName": family_name},
        DisplayName=f"{first_name} {family_name}",
    )
    assert result == "test_user_id"


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_get_user_id(mock_resolve_identity_store_id, mock_execute_aws_api_call):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = {"UserId": "test_user_id"}
    email = "test@example.com"
    user_name = email
    request = {
        "AlternateIdentifier": {
            "UniqueAttribute": {
                "AttributePath": "userName",
                "AttributeValue": user_name,
            },
        },
    }

    # Act
    result = identity_store.get_user_id(user_name)

    # Assert
    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "get_user_id",
        IdentityStoreId="test_instance_id",
        **request,
    )
    assert result == "test_user_id"


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_get_user_id_user_not_found(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    # Arrange
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = False
    user_name = "nonexistent_user"

    # Act
    result = identity_store.get_user_id(user_name)

    # Assert
    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "get_user_id",
        IdentityStoreId="test_instance_id",
        AlternateIdentifier={
            "UniqueAttribute": {
                "AttributePath": "userName",
                "AttributeValue": user_name,
            },
        },
    )
    assert result is False


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_delete_user(mock_resolve_identity_store_id, mock_execute_aws_api_call):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = {}
    user_id = "test_user_id"

    result = identity_store.delete_user(user_id)

    mock_execute_aws_api_call.assert_has_calls(
        [
            call(
                "identitystore",
                "delete_user",
                IdentityStoreId="test_instance_id",
                UserId=user_id,
            )
        ]
    )
    assert result is True


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_delete_user_not_found(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = False
    user_id = "nonexistent_user_id"

    result = identity_store.delete_user(user_id)

    mock_execute_aws_api_call.assert_has_calls(
        [
            call(
                "identitystore",
                "delete_user",
                IdentityStoreId="test_instance_id",
                UserId=user_id,
            )
        ]
    )
    assert result is False


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.utils.api.convert_string_to_camel_case")
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_users(mock_execute_aws_api_call, mock_convert_string_to_camel_case):
    mock_execute_aws_api_call.return_value = ["User1", "User2"]

    result = identity_store.list_users()

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_users",
        paginated=True,
        keys=["Users"],
        IdentityStoreId="test_instance_id",
    )
    assert result == ["User1", "User2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.utils.api.convert_string_to_camel_case")
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_users_with_identity_store_id(
    mock_execute_aws_api_call, mock_convert_string_to_camel_case
):
    mock_execute_aws_api_call.return_value = ["User1", "User2"]

    result = identity_store.list_users(identity_store_id="custom_instance_id")

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
        IdentityStoreId="test_instance_id",
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
        IdentityStoreId="test_instance_id",
    )

    assert result == ["Membership1", "Membership2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_group_memberships_with_custom_id(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = ["Membership1", "Membership2"]

    result = identity_store.list_group_memberships(
        "test_group_id", IdentityStoreId="custom_instance_id"
    )

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_group_memberships",
        ["GroupMemberships"],
        GroupId="test_group_id",
        IdentityStoreId="custom_instance_id",
    )

    assert result == ["Membership1", "Membership2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.list_group_memberships")
def test_list_groups_with_memberships(
    mock_list_group_memberships, mock_execute_aws_api_call
):
    mock_execute_aws_api_call.return_value = [
        {"GroupId": "Group1"},
        {"GroupId": "Group2"},
    ]
    mock_list_group_memberships.side_effect = [["Membership1"], ["Membership2"]]

    result = identity_store.list_groups_with_memberships()

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_groups",
        paginated=True,
        keys=["Groups"],
        IdentityStoreId="test_instance_id",
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
