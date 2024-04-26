# from unittest.mock import patch
from modules.provisioning import users


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


def test_users_without_filters(google_users, aws_users):
    source_users = {"users": google_users(4, "user", "test.com"), "key": "primaryEmail"}
    target_users = {"users": aws_users(3, "user", "test.com"), "key": "UserName"}

    users_to_create, users_to_delete = users.sync(source_users, target_users)

    assert users_to_create == [source_users["users"][3]]
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


def test_users_with_empty_source(aws_users):
    source_users = {"users": [], "key": "primaryEmail"}
    target_users = {"users": aws_users(3, "user", "test.com"), "key": "UserName"}
    users_to_create, users_to_delete = users.sync(source_users, target_users)
    assert users_to_create == []
    assert users_to_delete == []


def test_users_with_empty_target(google_users):
    source_users = {"users": google_users(4, "user", "test.com"), "key": "primaryEmail"}
    target_users = {"users": [], "key": "UserName"}
    users_to_create, users_to_delete = users.sync(source_users, target_users)
    assert users_to_create == source_users["users"]
    assert users_to_delete == []


def test_users_with_delete_target_all(aws_groups):
    source_users = {"users": [], "key": "primaryEmail"}
    target_users = {"users": aws_groups(3, "user", "test.com"), "key": "UserName"}
    users_to_create, users_to_delete = users.sync(
        source_users, target_users, delete_target_all=True
    )
    assert users_to_create == []
    assert users_to_delete == target_users["users"]
