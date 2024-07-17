import os
from unittest.mock import call, patch  # type: ignore
import pytest
from pytest import fixture
from integrations.aws import identity_store


@fixture
def user_number():
    return 1


@fixture
def user(user_number):
    number = user_number
    return {
        "UserName": f"test_user_{number}",
        "UserId": f"test_user_id_{number}",
        "ExternalIds": [
            {"Issuer": f"test_issuer_{number}", "Id": f"test_id_{number}"},
        ],
        "Name": {
            "Formatted": f"Test User {number}",
            "FamilyName": "User",
            "GivenName": "Test",
            "MiddleName": "T",
        },
        "DisplayName": f"Test User {number}",
        "Emails": [
            {
                "Value": f"test_user_{number}@example.com",
                "Type": "work",
                "Primary": True,
            },
        ],
    }


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


@patch("integrations.aws.identity_store.list_users")
def test_healtcheck_is_healthy(mock_list_users):
    mock_list_users.return_value = ["User1", "User2"]

    result = identity_store.healthcheck()

    assert result is True
    mock_list_users.assert_called_once


@patch("integrations.aws.identity_store.list_users")
def test_healtcheck_is_unhealthy(mock_list_users):
    mock_list_users.return_value = []

    result = identity_store.healthcheck()

    assert result is False
    mock_list_users.assert_called_once


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
def test_create_user_failed(mock_resolve_identity_store_id, mock_execute_aws_api_call):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = False
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
    assert result is False


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
def test_describe_user(
    mock_resolve_identity_store_id, mock_execute_aws_api_call, aws_users
):
    user = aws_users(1)[0]
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    user["ResponseMetadata"] = {"HTTPStatusCode": 200}
    mock_execute_aws_api_call.return_value = user
    user_id = "user_id1"

    expected = {
        "UserName": "user-email1@test.com",
        "UserId": "user_id1",
        "Name": {
            "FamilyName": "Family_name_1",
            "GivenName": "Given_name_1",
        },
        "DisplayName": "Given_name_1 Family_name_1",
        "Emails": [
            {
                "Value": "user-email1@test.com",
                "Type": "work",
                "Primary": True,
            }
        ],
    }

    result = identity_store.describe_user(user_id)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "describe_user",
        IdentityStoreId="test_instance_id",
        UserId="user_id1",
    )
    assert result == expected


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_describe_user_returns_false_if_not_found(
    mock_resolve_identity_store_id, mock_execute_aws_api_call, aws_users
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = False
    user_id = "nonexistent_user_id"

    result = identity_store.describe_user(user_id)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "describe_user",
        IdentityStoreId="test_instance_id",
        UserId="nonexistent_user_id",
    )
    assert result is False


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_delete_user(mock_resolve_identity_store_id, mock_execute_aws_api_call):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
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
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_users(mock_execute_aws_api_call):
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
@patch("integrations.utils.api.convert_string_to_pascal_case")
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_users_with_identity_store_id(
    mock_execute_aws_api_call, mock_convert_string_to_pascal_case
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
    )
    assert result == ["User1", "User2"]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_get_group_id(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = {"GroupId": "test_group_id"}
    group_name = "test_group_name"

    result = identity_store.get_group_id(group_name)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "get_group_id",
        IdentityStoreId="test_instance_id",
        AlternateIdentifier={
            "UniqueAttribute": {
                "AttributePath": "displayName",
                "AttributeValue": group_name,
            },
        },
    )
    assert result == "test_group_id"


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_get_group_id_no_group(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = False
    group_name = "nonexistent_group"

    result = identity_store.get_group_id(group_name)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "get_group_id",
        IdentityStoreId="test_instance_id",
        AlternateIdentifier={
            "UniqueAttribute": {
                "AttributePath": "displayName",
                "AttributeValue": group_name,
            },
        },
    )
    assert result is False


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
def test_list_groups_returns_empty_array_if_no_groups(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = False

    result = identity_store.list_groups()

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_groups",
        paginated=True,
        keys=["Groups"],
        IdentityStoreId="test_instance_id",
    )

    assert result == []


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
    )

    assert result == ["Group1", "Group2"]


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_create_group_membership(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = {
        "MembershipId": "test_membership_id",
        "IdentityStoreId": "test_instance_id",
    }
    group_id = "test_group_id"
    user_id = "test_user_id"

    # Act
    result = identity_store.create_group_membership(group_id, user_id)

    # Assert
    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "create_group_membership",
        IdentityStoreId="test_instance_id",
        GroupId=group_id,
        MemberId={"UserId": user_id},
    )
    assert result == "test_membership_id"


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_create_group_membership_unsuccessful(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = False
    group_id = "test_group_id"
    user_id = "test_user_id"

    result = identity_store.create_group_membership(group_id, user_id)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "create_group_membership",
        IdentityStoreId="test_instance_id",
        GroupId=group_id,
        MemberId={"UserId": user_id},
    )
    assert result is False


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_get_group_membership_id(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = {
        "MembershipId": "test_membership_id",
        "IdentityStoreId": "test_instance_id",
    }
    group_id = "test_group_id"
    user_id = "test_user_id"

    result = identity_store.get_group_membership_id(group_id, user_id)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "get_group_membership_id",
        IdentityStoreId="test_instance_id",
        GroupId=group_id,
        MemberId={"UserId": user_id},
    )
    assert result == "test_membership_id"


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_get_group_membership_id_returns_false_if_not_found(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = False
    group_id = "test_group_id"
    user_id = "test_user_id"

    result = identity_store.get_group_membership_id(group_id, user_id)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "get_group_membership_id",
        IdentityStoreId="test_instance_id",
        GroupId=group_id,
        MemberId={"UserId": user_id},
    )
    assert result is False


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_delete_group_membership(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    mock_execute_aws_api_call.return_value = {
        "ResponseMetadata": {"HTTPStatusCode": 200}
    }
    membership_id = "test_membership_id"

    result = identity_store.delete_group_membership(membership_id)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "delete_group_membership",
        IdentityStoreId="test_instance_id",
        MembershipId=membership_id,
    )
    assert result is True


@patch("integrations.aws.identity_store.execute_aws_api_call")
@patch("integrations.aws.identity_store.resolve_identity_store_id")
def test_delete_group_membership_resource_not_found(
    mock_resolve_identity_store_id, mock_execute_aws_api_call
):
    mock_resolve_identity_store_id.return_value = {
        "IdentityStoreId": "test_instance_id"
    }
    # API error handling should return False if the resource is not found
    mock_execute_aws_api_call.return_value = False
    membership_id = "nonexistent_membership_id"

    result = identity_store.delete_group_membership(membership_id)

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "delete_group_membership",
        IdentityStoreId="test_instance_id",
        MembershipId=membership_id,
    )
    assert result is False


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_group_memberships(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = [
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership1",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User1"},
        },
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership2",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User2"},
        },
    ]

    result = identity_store.list_group_memberships("test_group_id")

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_group_memberships",
        paginated=True,
        keys=["GroupMemberships"],
        GroupId="test_group_id",
        IdentityStoreId="test_instance_id",
    )

    assert result == [
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership1",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User1"},
        },
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership2",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User2"},
        },
    ]


@patch.dict(os.environ, {"AWS_SSO_INSTANCE_ID": "test_instance_id"})
@patch("integrations.aws.identity_store.execute_aws_api_call")
def test_list_group_memberships_with_custom_id(mock_execute_aws_api_call):
    mock_execute_aws_api_call.return_value = [
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership1",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User1"},
        },
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership2",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User2"},
        },
    ]
    result = identity_store.list_group_memberships(
        "test_group_id", IdentityStoreId="custom_instance_id"
    )

    mock_execute_aws_api_call.assert_called_once_with(
        "identitystore",
        "list_group_memberships",
        paginated=True,
        keys=["GroupMemberships"],
        GroupId="test_group_id",
        IdentityStoreId="custom_instance_id",
    )

    assert result == [
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership1",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User1"},
        },
        {
            "IdentityStoreId": "test_instance_id",
            "MembershipId": "Membership2",
            "GroupId": "test_group_id",
            "MemberId": {"UserId": "User2"},
        },
    ]


@patch("integrations.aws.identity_store.list_groups")
@patch("integrations.aws.identity_store.list_group_memberships")
@patch("integrations.aws.identity_store.describe_user")
def test_list_groups_with_memberships(
    mock_describe_user,
    mock_list_group_memberships,
    mock_list_groups,
    aws_groups,
    aws_groups_memberships,
    aws_users,
):
    groups = aws_groups(2, prefix="test-")
    memberships = [
        [],
        aws_groups_memberships(2, prefix="test-", group_id=2)["GroupMemberships"],
    ]
    users = aws_users(2, prefix="test-", domain="test.com")
    expected_output = [
        {
            "Description": "A group to test resolving AWS-group1 memberships",
            "DisplayName": "test-group-name1",
            "GroupId": "test-aws-group_id1",
            "GroupMemberships": [],
            "IdentityStoreId": "d-123412341234",
        },
        {
            "GroupId": "test-aws-group_id2",
            "DisplayName": "test-group-name2",
            "Description": "A group to test resolving AWS-group2 memberships",
            "IdentityStoreId": "d-123412341234",
            "GroupMemberships": [
                {
                    "IdentityStoreId": "d-123412341234",
                    "MembershipId": "test-membership_id_1",
                    "GroupId": "test-aws-group_id2",
                    "MemberId": {
                        "UserName": "test-user-email1@test.com",
                        "UserId": "test-user_id1",
                        "Name": {
                            "FamilyName": "Family_name_1",
                            "GivenName": "Given_name_1",
                        },
                        "DisplayName": "Given_name_1 Family_name_1",
                        "Emails": [
                            {
                                "Value": "test-user-email1@test.com",
                                "Type": "work",
                                "Primary": True,
                            }
                        ],
                        "IdentityStoreId": "d-123412341234",
                    },
                },
                {
                    "IdentityStoreId": "d-123412341234",
                    "MembershipId": "test-membership_id_2",
                    "GroupId": "test-aws-group_id2",
                    "MemberId": {
                        "UserName": "test-user-email2@test.com",
                        "UserId": "test-user_id2",
                        "Name": {
                            "FamilyName": "Family_name_2",
                            "GivenName": "Given_name_2",
                        },
                        "DisplayName": "Given_name_2 Family_name_2",
                        "Emails": [
                            {
                                "Value": "test-user-email2@test.com",
                                "Type": "work",
                                "Primary": True,
                            }
                        ],
                        "IdentityStoreId": "d-123412341234",
                    },
                },
            ],
        },
    ]
    mock_list_groups.return_value = groups

    mock_list_group_memberships.side_effect = memberships

    user_side_effect = []
    for user in users:
        user_side_effect.append(user)

    mock_describe_user.side_effect = user_side_effect

    result = identity_store.list_groups_with_memberships()

    assert result == expected_output


@patch("integrations.aws.identity_store.list_groups")
@patch("integrations.aws.identity_store.list_group_memberships")
@patch("integrations.aws.identity_store.describe_user")
def test_list_groups_with_memberships_empty_groups(
    mock_describe_user,
    mock_list_group_memberships,
    mock_list_groups,
):
    mock_list_groups.return_value = []
    result = identity_store.list_groups_with_memberships()
    assert result == []
    assert mock_list_group_memberships.call_count == 0
    assert mock_describe_user.call_count == 0


@patch("integrations.aws.identity_store.list_groups")
@patch("integrations.aws.identity_store.list_group_memberships")
@patch("integrations.aws.identity_store.describe_user")
def test_list_groups_with_memberships_empty_groups_memberships_with_flag(
    mock_describe_user, mock_list_group_memberships, mock_list_groups, aws_groups
):
    groups = aws_groups(2, prefix="test-")
    expected_output = []
    groups_memberships = [[], []]
    mock_list_groups.return_value = groups
    mock_list_group_memberships.side_effect = groups_memberships
    result = identity_store.list_groups_with_memberships(include_empty_groups=False)
    assert result == expected_output
    assert mock_list_group_memberships.call_count == 2
    assert mock_describe_user.call_count == 0


@patch("integrations.aws.identity_store.filters.filter_by_condition")
@patch("integrations.aws.identity_store.list_groups")
@patch("integrations.aws.identity_store.list_group_memberships")
@patch("integrations.aws.identity_store.describe_user")
def test_list_groups_with_memberships_filtered(
    mock_describe_user,
    mock_list_group_memberships,
    mock_list_groups,
    mock_filter_by_condition,
    aws_groups,
    aws_groups_memberships,
    aws_users,
):
    groups = aws_groups(2, prefix="test-")
    groups_to_filter_out = aws_groups(4)[2:]
    groups.extend(groups_to_filter_out)
    memberships = [
        [],
        aws_groups_memberships(2, prefix="test-", group_id=2)["GroupMemberships"],
    ]
    users = aws_users(2, prefix="test-", domain="test.com")

    expected_output = [
        {
            "Description": "A group to test resolving AWS-group1 memberships",
            "DisplayName": "test-group-name1",
            "GroupId": "test-aws-group_id1",
            "GroupMemberships": [],
            "IdentityStoreId": "d-123412341234",
        },
        {
            "GroupId": "test-aws-group_id2",
            "DisplayName": "test-group-name2",
            "Description": "A group to test resolving AWS-group2 memberships",
            "IdentityStoreId": "d-123412341234",
            "GroupMemberships": [
                {
                    "IdentityStoreId": "d-123412341234",
                    "MembershipId": "test-membership_id_1",
                    "GroupId": "test-aws-group_id2",
                    "MemberId": {
                        "UserName": "test-user-email1@test.com",
                        "UserId": "test-user_id1",
                        "Name": {
                            "FamilyName": "Family_name_1",
                            "GivenName": "Given_name_1",
                        },
                        "DisplayName": "Given_name_1 Family_name_1",
                        "Emails": [
                            {
                                "Value": "test-user-email1@test.com",
                                "Type": "work",
                                "Primary": True,
                            }
                        ],
                        "IdentityStoreId": "d-123412341234",
                    },
                },
                {
                    "IdentityStoreId": "d-123412341234",
                    "MembershipId": "test-membership_id_2",
                    "GroupId": "test-aws-group_id2",
                    "MemberId": {
                        "UserName": "test-user-email2@test.com",
                        "UserId": "test-user_id2",
                        "Name": {
                            "FamilyName": "Family_name_2",
                            "GivenName": "Given_name_2",
                        },
                        "DisplayName": "Given_name_2 Family_name_2",
                        "Emails": [
                            {
                                "Value": "test-user-email2@test.com",
                                "Type": "work",
                                "Primary": True,
                            }
                        ],
                        "IdentityStoreId": "d-123412341234",
                    },
                },
            ],
        },
    ]
    mock_list_groups.return_value = groups

    mock_list_group_memberships.side_effect = memberships

    user_side_effect = []
    for user in users:
        user_side_effect.append(user)

    mock_describe_user.side_effect = user_side_effect
    mock_filter_by_condition.return_value = groups[:2]
    groups_filters = [lambda group: "test-" in group["DisplayName"]]
    result = identity_store.list_groups_with_memberships(groups_filters=groups_filters)

    assert mock_filter_by_condition.call_count == 1
    assert mock_list_group_memberships.call_count == 2
    assert mock_describe_user.call_count == 2
    assert result == expected_output


@patch("integrations.aws.identity_store.list_groups")
@patch("integrations.aws.identity_store.list_group_memberships")
@patch("integrations.aws.identity_store.describe_user")
def test_list_groups_with_memberhips_without_members_enabled(
    mock_describe_user,
    mock_list_group_memberships,
    mock_list_groups,
    aws_groups,
    aws_groups_memberships,
):
    groups = aws_groups(2, prefix="test-")
    memberships = [
        [],
        aws_groups_memberships(2, prefix="test-", group_id=2)["GroupMemberships"],
    ]
    expected_output = [
        {
            "Description": "A group to test resolving AWS-group1 memberships",
            "DisplayName": "test-group-name1",
            "GroupId": "test-aws-group_id1",
            "IdentityStoreId": "d-123412341234",
        },
        {
            "GroupId": "test-aws-group_id2",
            "DisplayName": "test-group-name2",
            "Description": "A group to test resolving AWS-group2 memberships",
            "IdentityStoreId": "d-123412341234",
        },
    ]
    mock_list_groups.return_value = groups
    mock_list_group_memberships.side_effect = memberships

    result = identity_store.list_groups_with_memberships(group_members=False)

    assert result == expected_output
    assert mock_list_group_memberships.call_count == 0
    assert mock_describe_user.call_count == 0
