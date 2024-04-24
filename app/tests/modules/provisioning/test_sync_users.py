# from unittest.mock import patch
from pytest import fixture

from modules.provisioning import sync_users


@fixture
def source_groups():
    return [
        {
            "id": "source_group_id1",
            "name": "SOURCE-group1",
            "email": "SOURCE-group1@test.com",
            "members": [
                {"email": "user1.test@test.com", "id": "user1_id"},
                {"email": "user2.test@test.com", "id": "user2_id"},
                {"email": "user3.test@test.com", "id": "user3_id"},
            ],
        },
        {
            "id": "source_group_id2",
            "name": "SOURCE-group2",
            "email": "SOURCE-group2@test.com",
            "members": [
                {"email": "user1.test@test.com", "id": "user1_id"},
                {"email": "user2.test@test.com", "id": "user2_id"},
                {"email": "user9.test@external.com", "id": "user9_external_id"},
            ],
        },
        {
            "id": "source_group_id3",
            "name": "SOURCEgroup3",
            "email": "sourcegroup3@test.com",
        },
    ]


def target_groups():
    return [
        {
            "GroupId": "target_group_id1",
            "DisplayName": "group1",
            "Memberships": [
                {
                    "Email": [{"user1.test@test.com"}],
                    "id": "user1_id",
                    "Name": {"GivenName": "User1", "FamilyName": "Test"},
                },
            ],
        },
        {
            "GroupId": "target_group_id2",
            "DisplayName": "group2",
        },
    ]


@fixture
def source_users():
    return {
        "users": [
            {
                "email": "user1.test@test.com",
                "id": "user1_id",
                "name": {
                    "givenName": "User1",
                    "familyName": "Test",
                    "fullName": "User1 Test",
                },
            },
            {
                "email": "user2.test@test.com",
                "id": "user2_id",
                "name": {
                    "givenName": "User2",
                    "familyName": "Test",
                    "fullName": "User2 Test",
                },
            },
            {
                "email": "user3.test@test.com",
                "id": "user3_id",
                "name": {
                    "givenName": "User3",
                    "familyName": "Test",
                    "fullName": "User3 Test",
                },
            },
            {
                "email": "user9.test@external.com",
                "id": "user9_external_id",
                "name": {
                    "givenName": "User9",
                    "familyName": "Test",
                    "fullName": "User9 Test",
                },
            },
        ],
        "key": "email",
    }


@fixture
def target_users():
    return {
        "users": [
            {
                "UserName": "user1.test@test.com",
                "UserId": "user1_id",
                "Name": {"GivenName": "User1", "FamilyName": "Test"},
                "DisplayName": "User1 Test",
                "Emails": [
                    {"Value": "user1.test@test.com", "Type": "work", "Primary": True}
                ],
            },
        ],
        "key": "UserName",
    }


def test_filter_by_condition():
    list = [1, 2, 3, 4, 5]

    def condition(x):
        return x % 2 == 0

    assert sync_users.filter_by_condition(list, condition) == [2, 4]


def test_filter_by_condition_with_dict_list():
    list = [
        {"name": "User1", "username": "username1"},
        {"name": "User2", "username": "username2"},
    ]
    assert sync_users.filter_by_condition(list, lambda x: x["name"] == "User1") == [
        {"name": "User1", "username": "username1"}
    ]


def test_filter_by_condition_filters_out_on_empty_list():
    list = []
    assert sync_users.filter_by_condition(list, lambda x: x["name"] == "User1") == []


def test_filter_by_condition_filters_against_key_list_values():
    list = [
        {"name": "User1", "username": "username1"},
        {"name": "User2", "username": "username2"},
        {"name": "User3", "username": "username3"},
        {"name": "User4", "username": "username4"},
        {"name": "User5", "username": "username5"},
    ]
    values = ["User1", "User3", "User5"]
    assert sync_users.filter_by_condition(list, lambda x: x["name"] in values) == [
        {"name": "User1", "username": "username1"},
        {"name": "User3", "username": "username3"},
        {"name": "User5", "username": "username5"},
    ]


def test_filter_by_condition_filters_out_against_key_list_values():
    list = [
        {"name": "User1", "username": "username1"},
        {"name": "User2", "username": "username2"},
        {"name": "User3", "username": "username3"},
        {"name": "User4", "username": "username4"},
        {"name": "User5", "username": "username5"},
    ]
    values = ["User1", "User3", "User5"]
    assert sync_users.filter_by_condition(list, lambda x: x["name"] not in values) == [
        {"name": "User2", "username": "username2"},
        {"name": "User4", "username": "username4"},
    ]


def test_get_nested_value():
    user = {"name": {"givenName": "User1", "familyName": "Test"}}
    assert sync_users.get_nested_value(user, "name.givenName") == "User1"


def test_get_nested_value_with_empty_key():
    user = {"name": {"givenName": "User1", "familyName": "Test"}}
    assert sync_users.get_nested_value(user, "") is None


def test_get_nested_value_with_empty_dict():
    user = {}
    assert sync_users.get_nested_value(user, "name.givenName") is None


def test_get_nested_value_with_nested_list():
    user = {
        "name": {"givenName": "User1", "familyName": "Test"},
        "emails": [{"value": "test@test.com", "type": "work", "primary": True}],
    }

    assert sync_users.get_nested_value(user, "name.emails.1.value") is None


def test_get_unique_users_from_groups(source_groups):
    users = sync_users.get_unique_users_from_groups(source_groups, "members")
    expected_users = [
        {"email": "user1.test@test.com", "id": "user1_id"},
        {"email": "user2.test@test.com", "id": "user2_id"},
        {"email": "user3.test@test.com", "id": "user3_id"},
        {"email": "user9.test@external.com", "id": "user9_external_id"},
    ]

    assert sorted(users, key=lambda user: user["id"]) == sorted(
        expected_users, key=lambda user: user["id"]
    )


def test_sync_users_without_filters(source_users, target_users):
    users_to_create, users_to_delete = sync_users.sync_users(source_users, target_users)

    assert users_to_create == [
        {
            "email": "user2.test@test.com",
            "id": "user2_id",
            "name": {
                "givenName": "User2",
                "familyName": "Test",
                "fullName": "User2 Test",
            },
        },
        {
            "email": "user3.test@test.com",
            "id": "user3_id",
            "name": {
                "givenName": "User3",
                "familyName": "Test",
                "fullName": "User3 Test",
            },
        },
        {
            "email": "user9.test@external.com",
            "id": "user9_external_id",
            "name": {
                "givenName": "User9",
                "familyName": "Test",
                "fullName": "User9 Test",
            },
        },
    ]
    assert users_to_delete == []


def test_sync_users_with_filters(source_users, target_users):
    filters = [lambda user: "@test.com" in user["email"]]
    users_to_create, users_to_delete = sync_users.sync_users(
        source_users, target_users, filters=filters
    )
    assert users_to_create == [
        {
            "email": "user2.test@test.com",
            "id": "user2_id",
            "name": {
                "givenName": "User2",
                "familyName": "Test",
                "fullName": "User2 Test",
            },
        },
        {
            "email": "user3.test@test.com",
            "id": "user3_id",
            "name": {
                "givenName": "User3",
                "familyName": "Test",
                "fullName": "User3 Test",
            },
        },
    ]
    assert users_to_delete == []


def test_sync_users_with_empty_source(source_users, target_users):
    source_users["users"] = []
    users_to_create, users_to_delete = sync_users.sync_users(source_users, target_users)
    assert users_to_create == []
    assert users_to_delete == []


def test_sync_users_with_empty_target(source_users, target_users):
    target_users["users"] = []
    users_to_create, users_to_delete = sync_users.sync_users(source_users, target_users)
    assert users_to_create == source_users["users"]
    assert users_to_delete == []


def test_sync_users_with_delete_target_all(source_users, target_users):
    users_to_create, users_to_delete = sync_users.sync_users(
        source_users, target_users, delete_target_all=True
    )
    assert users_to_create == []
    assert users_to_delete == target_users["users"]
