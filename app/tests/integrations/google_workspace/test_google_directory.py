"""Unit tests for google_directory module."""
from unittest.mock import patch, MagicMock

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
    # Mock the first page of results
    first_page = {
        "users": [
            {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        ],
        "nextPageToken": "token",
    }

    # Mock the second page of results
    second_page = {
        "users": [
            {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
        ]
    }

    # Mock the list method to return the first page of results
    list_mock = MagicMock()
    list_mock.execute.return_value = first_page
    get_google_service_mock.return_value.users.return_value.list.return_value = list_mock

    # Mock the list_next method to return a new request that returns the second page of results the first time it's called,
    # and None the second time it's called
    second_page_request = MagicMock()
    second_page_request.execute.return_value = second_page
    list_next_mock = MagicMock(side_effect=[second_page_request, None])
    get_google_service_mock.return_value.users.return_value.list_next = list_next_mock

    assert google_directory.list_users() == [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]


# @patch("integrations.google_workspace.google_directory.get_google_service")
# def test_list_users_iterates_over_pages(get_google_service_mock):
#     get_google_service_mock.return_value.users.return_value.list.return_value.execute.side_effect = [
#         {
#             "users": [
#                 {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"}
#             ],
#             "nextPageToken": "token",
#         },
#         {
#             "users": [
#                 {
#                     "id": "test_user_id2",
#                     "name": "test_user2",
#                     "email": "email2@domain.com",
#                 }
#             ]
#         },
#     ]

#     assert google_directory.list_users() == [
#         {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
#         {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
#     ]


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
