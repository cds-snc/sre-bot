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
