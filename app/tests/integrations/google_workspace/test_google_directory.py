"""Unit tests for google_directory module."""
from unittest.mock import patch

import integrations.google_workspace.google_directory as google_directory


@patch("integrations.google_workspace.google_directory.get_google_service")
def test_get_user_returns_user(get_google_service_mock):
    get_google_service_mock.return_value.users.return_value.get.return_value.execute.return_value = {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }

    assert google_directory.get_user("test_user_id") == {
        "id": "test_user_id",
        "name": "test_user",
        "email": "user.name@domain.com",
    }


@patch("integrations.google_workspace.google_directory.get_google_service")
def test_list_users_returns_users(get_google_service_mock):
    get_google_service_mock.return_value.users.return_value.list.return_value.execute.return_value = {
        "users": [
            {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
            {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
        ]
    }

    assert google_directory.list_users() == [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]


@patch("integrations.google_workspace.google_directory.get_google_service")
def test_list_users_iterates_over_pages(get_google_service_mock):
    get_google_service_mock.return_value.users.return_value.list.return_value.execute.side_effect = [
        {
            "users": [
                {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"}
            ],
            "nextPageToken": "token",
        },
        {
            "users": [
                {
                    "id": "test_user_id2",
                    "name": "test_user2",
                    "email": "email2@domain.com",
                }
            ]
        },
    ]

    assert google_directory.list_users() == [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]


@patch("integrations.google_workspace.google_directory.get_google_service")
def test_list_groups_returns_groups(get_google_service_mock):
    get_google_service_mock.return_value.groups.return_value.list.return_value.execute.return_value = {
        "groups": [
            {"id": "test_group_id", "name": "test_group"},
            {"id": "test_group_id2", "name": "test_group2"},
        ]
    }

    assert google_directory.list_groups() == [
        {"id": "test_group_id", "name": "test_group"},
        {"id": "test_group_id2", "name": "test_group2"},
    ]


@patch("integrations.google_workspace.google_directory.get_google_service")
def test_list_groups_iterates_over_pages(get_google_service_mock):
    get_google_service_mock.return_value.groups.return_value.list.return_value.execute.side_effect = [
        {
            "groups": [{"id": "test_group_id", "name": "test_group"}],
            "nextPageToken": "token",
        },
        {
            "groups": [{"id": "test_group_id2", "name": "test_group2"}],
        },
    ]

    assert google_directory.list_groups() == [
        {"id": "test_group_id", "name": "test_group"},
        {"id": "test_group_id2", "name": "test_group2"},
    ]


@patch("integrations.google_workspace.google_directory.get_google_service")
def test_list_group_members_returns_group_members(get_google_service_mock):
    get_google_service_mock.return_value.members.return_value.list.return_value.execute.return_value = {
        "members": [
            {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
            {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
        ]
    }

    assert google_directory.list_group_members("test_group_id") == [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]


@patch("integrations.google_workspace.google_directory.get_google_service")
def test_list_group_members_iterates_over_pages(get_google_service_mock):
    get_google_service_mock.return_value.members.return_value.list.return_value.execute.side_effect = [
        {
            "members": [
                {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"}
            ],
            "nextPageToken": "token",
        },
        {
            "members": [
                {
                    "id": "test_user_id2",
                    "name": "test_user2",
                    "email": "email2@domain.com",
                }
            ],
        },
    ]

    assert google_directory.list_group_members("test_group_id") == [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]
