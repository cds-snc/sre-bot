from utils import filters


def test_filter_by_condition():
    list = [1, 2, 3, 4, 5]

    def condition(x):
        return x % 2 == 0

    assert filters.filter_by_condition(list, condition) == [2, 4]


def test_filter_by_condition_with_dict_list():
    list = [
        {"name": "User1", "username": "username1"},
        {"name": "User2", "username": "username2"},
    ]
    assert filters.filter_by_condition(list, lambda x: x["name"] == "User1") == [
        {"name": "User1", "username": "username1"}
    ]


def test_filter_by_condition_filters_out_on_empty_list():
    list = []
    assert filters.filter_by_condition(list, lambda x: x["name"] == "User1") == []


def test_filter_by_condition_filters_against_key_list_values():
    list = [
        {"name": "User1", "username": "username1"},
        {"name": "User2", "username": "username2"},
        {"name": "User3", "username": "username3"},
        {"name": "User4", "username": "username4"},
        {"name": "User5", "username": "username5"},
    ]
    values = ["User1", "User3", "User5"]
    assert filters.filter_by_condition(list, lambda x: x["name"] in values) == [
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
    assert filters.filter_by_condition(list, lambda x: x["name"] not in values) == [
        {"name": "User2", "username": "username2"},
        {"name": "User4", "username": "username4"},
    ]


def test_get_nested_value():
    user = {"name": {"givenName": "User1", "familyName": "Test"}}
    assert filters.get_nested_value(user, "name.givenName") == "User1"


def test_get_nested_value_with_empty_key():
    user = {"name": {"givenName": "User1", "familyName": "Test"}}
    assert filters.get_nested_value(user, "") is None


def test_get_nested_value_with_empty_dict():
    user = {}
    assert filters.get_nested_value(user, "name.givenName") is None


def test_get_nested_value_with_nested_list():
    user = {
        "name": {"givenName": "User1", "familyName": "Test"},
        "emails": [{"value": "test@test.com", "type": "work", "primary": True}],
    }

    assert filters.get_nested_value(user, "name.emails.1.value") is None


def test_compare_lists_default():
    source = {
        "key": "userName",
        "values": [{"userName": "user1"}, {"userName": "user2"}],
    }
    target = {
        "key": "DisplayName",
        "values": [{"DisplayName": "user1"}, {"DisplayName": "user2"}],
    }

    users_to_create, users_to_delete = filters.compare_lists(source, target)
    assert users_to_create == []
    assert users_to_delete == []


def test_compare_lists_with_different_values():
    source = {
        "key": "userName",
        "values": [{"userName": "user1"}, {"userName": "user2"}],
    }
    target = {
        "key": "DisplayName",
        "values": [{"DisplayName": "user1"}, {"DisplayName": "user3"}],
    }

    users_to_create, users_to_delete = filters.compare_lists(source, target)
    assert users_to_create == [{"userName": "user2"}]
    assert users_to_delete == [{"DisplayName": "user3"}]


def test_compare_lists_match_mode():
    source = {
        "key": "userName",
        "values": [{"userName": "user1"}, {"userName": "user2"}],
    }
    target = {
        "key": "DisplayName",
        "values": [{"DisplayName": "user1"}, {"DisplayName": "user2"}],
    }

    source_values, target_values = filters.compare_lists(source, target, mode="match")
    assert source_values == source["values"]
    assert target_values == target["values"]
    assert len(source_values) == len(target_values)


def test_compare_lists_missing_key():
    source = {"values": [{"userName": "user1"}, {"userName": "user2"}]}
    target = {"key": "DisplayName", "values": [{"DisplayName": "user1"}]}

    response = filters.compare_lists(source, target)
    assert response == ([], [])
    response = filters.compare_lists(source, target, mode="match")
    assert response == ([], [])
    response = filters.compare_lists(source, target, mode="sync")
    assert response == ([], [])

    source = {
        "key": "userName",
        "values": [{"userName": "user1"}, {"userName": "user2"}],
    }
    target = {"values": [{"DisplayName": "user1"}]}

    response = filters.compare_lists(source, target)
    assert response == ([], [])
    response = filters.compare_lists(source, target, mode="match")
    assert response == ([], [])
    response = filters.compare_lists(source, target, mode="sync")
    assert response == ([], [])


def test_compare_list_with_complex_values_match_mode(google_groups, aws_groups):
    prefix = "aws-"
    source_values = google_groups(3, prefix, "test.com")
    for value in source_values:
        value["matching_key"] = (
            value["email"].replace(prefix, "").replace("@test.com", "")
        )
    source = {"values": source_values, "key": "matching_key"}

    target_values = aws_groups(5)
    target = {
        "values": target_values,
        "key": "DisplayName",
    }

    response = filters.compare_lists(source, target, mode="match")

    assert response == (source["values"], target["values"][:3])


def test_compare_list_with_complex_values_sync_mode(google_users, aws_users):
    source_users = google_users(3, "user", "test.com")
    target_users = aws_users(5, "user", "test.com")

    source = {"values": source_users, "key": "primaryEmail"}
    target = {"values": target_users, "key": "UserName"}

    response = filters.compare_lists(source, target, mode="sync")

    assert response == ([], target["values"][3:])


def test_get_unique_nested_dicts(google_groups_w_users):
    groups = google_groups_w_users()
    unique_users = []
    for group in groups:
        for user in group["members"]:
            if user not in unique_users:
                unique_users.append(user)
    users_from_groups = filters.get_unique_nested_dicts(groups, "members")

    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        unique_users, key=lambda user: user["id"]
    )


def test_get_unique_nested_dicts_with_empty_source():
    groups = []
    users_from_groups = filters.get_unique_nested_dicts(groups, "members")
    assert users_from_groups == []


def test_get_unique_nested_dicts_from_single_dict(google_groups_w_users):
    source_group = google_groups_w_users()[0]
    users_from_groups = filters.get_unique_nested_dicts(source_group, "members")
    expected_users = source_group["members"]
    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        expected_users, key=lambda user: user["id"]
    )


def test_get_unique_nested_dicts_with_duplicate_key():
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
    users_from_groups = filters.get_unique_nested_dicts(group, "members")
    expected_users = [
        {"email": "user1.test@test.com", "id": "user1_id", "username": "user1"},
        {"email": "user2.test@test.com", "id": "user2_id", "username": "user1"},
        {"email": "user3.test@test.com", "id": "user3_id", "username": "user2"},
    ]
    assert sorted(users_from_groups, key=lambda user: user["id"]) == sorted(
        expected_users, key=lambda user: user["id"]
    )
