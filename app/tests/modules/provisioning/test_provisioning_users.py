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
