# from unittest.mock import patch
from pytest import fixture

from modules.provisioning import users


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


def test_get_unique_users_from_groups(google_groups_w_users):
    groups = google_groups_w_users()
    unique_users = []
    for group in groups:
        for user in group["members"]:
            if user not in unique_users:
                unique_users.append(user)
    users_from_groups = users.get_unique_users_from_groups(groups, "members")

    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        unique_users, key=lambda user: user["id"]
    )


def test_get_unique_users_from_groups_with_empty_groups():
    groups = []
    users_from_groups = users.get_unique_users_from_groups(groups, "members")
    assert users_from_groups == []


def test_get_unique_users_from_dict_group(google_groups_w_users):
    source_group = google_groups_w_users()[0]
    users_from_groups = users.get_unique_users_from_groups(source_group, "members")
    expected_users = source_group["members"]
    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        expected_users, key=lambda user: user["id"]
    )


def test_get_unique_users_from_dict_group_with_duplicate_key():
    group = {
        "id": "source_group_id1",
        "name": "SOURCE-group1",
        "email": "SOURCE-group1@test.com",
        "members": [
            {"email": "user1.test@test.com", "id": "user1_id", "username": "user1"},
            {"email": "user2.test@test.com", "id": "user2_id", "username": "user1"},
            {"email": "user3.test@test.com", "id": "user3_id", "username": "user2"},
        ],
    }
    users_from_groups = users.get_unique_users_from_groups(group, "members")
    expected_users = [
        {"email": "user1.test@test.com", "id": "user1_id", "username": "user1"},
        {"email": "user2.test@test.com", "id": "user2_id", "username": "user1"},
        {"email": "user3.test@test.com", "id": "user3_id", "username": "user2"},
    ]
    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        expected_users, key=lambda user: user["id"]
    )


def test_users_without_filters(source_users, target_users):
    users_to_create, users_to_delete = users.sync(source_users, target_users)

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


def test_users_with_filters(google_users, aws_users):
    source_users_to_include = google_users(4, "user", "test.com")
    non_matching_users = google_users(3, "user", "external.com")
    source_users = {
        "users": source_users_to_include + non_matching_users,
        "key": "primaryEmail",
    }
    matching_aws_users = aws_users(3, "user", "test.com")
    non_matching_aws_users = aws_users(3, "else", "test_outside.com")
    target_users = {
        "users": matching_aws_users + non_matching_aws_users,
        "key": "UserName",
    }
    filters = [lambda user: "@test.com" in user["primaryEmail"]]
    users_to_create, users_to_delete = users.sync(
        source_users, target_users, filters=filters
    )
    assert users_to_create == [source_users_to_include[3]]
    assert users_to_delete == []


def test_users_with_empty_source(source_users, target_users):
    source_users["users"] = []
    users_to_create, users_to_delete = users.sync(source_users, target_users)
    assert users_to_create == []
    assert users_to_delete == []


def test_users_with_empty_target(source_users, target_users):
    target_users["users"] = []
    users_to_create, users_to_delete = users.sync(source_users, target_users)
    assert users_to_create == source_users["users"]
    assert users_to_delete == []


def test_users_with_delete_target_all(source_users, target_users):
    users_to_create, users_to_delete = users.sync(
        source_users, target_users, delete_target_all=True
    )
    assert users_to_create == []
    assert users_to_delete == target_users["users"]
