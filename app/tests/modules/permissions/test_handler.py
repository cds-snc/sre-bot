from unittest.mock import patch
from modules.permissions import handler


@patch("modules.permissions.handler.google_directory.list_group_members")
def test_is_user_member_of_groups_returns_true_if_found(mock_list_group_members):
    mock_list_group_members.side_effect = [
        [{"email": "user.name1@email.com"}, {"email": "user.name2@email.com"}],
        [{"email": "user.name4@email.com"}, {"email": "user.name8@email.com"}],
    ]
    user_key = "user.name1@email.com"

    groups_keys = ["group_id_1", "group_id_2"]
    result = handler.is_user_member_of_groups(user_key, groups_keys)
    assert result is True


@patch("modules.permissions.handler.google_directory.list_group_members")
def test_is_user_member_of_groups_returns_false_if_not_found(mock_list_group_members):
    mock_list_group_members.side_effect = [
        [{"email": "user.name1@email.com"}, {"email": "user.name2@email.com"}],
        None,
        [{"email": "user.name4@email.com"}, {"email": "user.name8@email.com"}],
    ]
    user_key = "user.name3@email.com"
    group_keys = ["group_id_1", "group_id_2", "group_id_3"]
    result = handler.is_user_member_of_groups(user_key, group_keys)
    assert result is False


@patch("modules.permissions.handler.google_directory.list_group_members")
def test_get_authorizers_from_groups_returns_list_of_emails(mock_list_group_members):
    mock_list_group_members.side_effect = [
        [{"email": "user.name1@email.com"}, {"email": "user.name2@email.com"}],
        [{"email": "user.name4@email.com"}, {"email": "user.name8@email.com"}],
    ]
    groups_keys = ["group_id_1", "group_id_2"]
    result = handler.get_authorizers_from_groups(groups_keys)
    assert result == [
        "user.name1@email.com",
        "user.name2@email.com",
        "user.name4@email.com",
        "user.name8@email.com",
    ]


@patch("modules.permissions.handler.google_directory.list_group_members")
def test_get_authorizers_from_groups_returns_empty_list_if_no_members(
    mock_list_group_members,
):
    mock_list_group_members.side_effect = [None, None]
    groups_keys = ["group_id_1", "group_id_2"]
    result = handler.get_authorizers_from_groups(groups_keys)
    assert result == []
