"""Unit tests for google_directory module (factory-built, stub-typed Resource path)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from integrations.google_workspace import client as google_client
from integrations.google_workspace import google_directory

USER_READONLY_SCOPES = ["https://www.googleapis.com/auth/admin.directory.user.readonly"]
GROUP_READONLY_SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.readonly"]


def _http_error(status: int, reason: str = "boom") -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = reason

    return HttpError(resp=FakeResp(), content=b"{}")


@pytest.fixture
def directory_client(monkeypatch):
    """Patch the Admin Directory factory and expose the mocked Resource chain."""
    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_client, "get_admin_directory_service", factory)
    users = service.users.return_value
    groups = service.groups.return_value
    members = service.members.return_value
    for resource in (users, groups, members):
        resource.list_next.return_value = None
    return SimpleNamespace(
        factory=factory,
        service=service,
        users=users,
        groups=groups,
        members=members,
    )


def _set_pages(resource, pages: list[dict]) -> list[MagicMock]:
    """Wire resource.list/list_next so each page is returned by a distinct request mock."""
    requests = [MagicMock(name=f"request_{index}") for index in range(len(pages))]
    for request, page in zip(requests, pages, strict=True):
        request.execute.return_value = page
    resource.list.return_value = requests[0]
    resource.list_next.side_effect = list(requests[1:]) + [None]
    return requests


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
def test_list_users_returns_users(directory_client):
    users = [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]
    _set_pages(directory_client.users, [{"users": users}])

    assert google_directory.list_users() == users

    directory_client.factory.assert_called_once_with(scopes=USER_READONLY_SCOPES, delegated_user_email=None)
    directory_client.users.list.assert_called_once_with(
        customer="default_google_workspace_customer_id",
        maxResults=500,
        orderBy="email",
    )


def test_list_users_uses_custom_delegated_user_email_and_customer_id_if_provided(directory_client):
    users = [
        {"id": "test_user_id", "name": "test_user", "email": "email@domain.com"},
        {"id": "test_user_id2", "name": "test_user2", "email": "email2@domain.com"},
    ]
    _set_pages(directory_client.users, [{"users": users}])

    result = google_directory.list_users(
        delegated_user_email="custom.email@domain.com",
        customer="custom_customer_id",
    )

    assert result == users
    directory_client.factory.assert_called_once_with(
        scopes=USER_READONLY_SCOPES,
        delegated_user_email="custom.email@domain.com",
    )
    directory_client.users.list.assert_called_once_with(
        customer="custom_customer_id",
        maxResults=500,
        orderBy="email",
    )


def test_list_users_concatenates_pages(directory_client):
    _set_pages(
        directory_client.users,
        [
            {"users": [{"id": "user1"}], "nextPageToken": "token"},
            {"users": [{"id": "user2"}]},
        ],
    )

    assert google_directory.list_users() == [{"id": "user1"}, {"id": "user2"}]
    assert directory_client.users.list.call_count == 1


def test_list_users_skips_page_without_response_key(directory_client):
    _set_pages(
        directory_client.users,
        [
            {"nextPageToken": "token"},
            {"users": [{"id": "user2"}]},
        ],
    )

    assert google_directory.list_users() == [{"id": "user2"}]


def test_list_users_propagates_http_error(directory_client):
    error = _http_error(429)
    directory_client.users.list.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_directory.list_users()

    assert exc_info.value is error


@patch(
    "integrations.google_workspace.google_directory.GOOGLE_WORKSPACE_CUSTOMER_ID",
    new="default_google_workspace_customer_id",
)
def test_list_groups_calls_directory_groups_list(directory_client):
    _set_pages(directory_client.groups, [{"groups": [{"id": "test_group_id"}]}])

    assert google_directory.list_groups() == [{"id": "test_group_id"}]

    directory_client.factory.assert_called_once_with(scopes=GROUP_READONLY_SCOPES, delegated_user_email=None)
    directory_client.groups.list.assert_called_once_with(
        customer="default_google_workspace_customer_id",
        maxResults=200,
        orderBy="email",
    )


def test_list_groups_uses_custom_delegated_user_email_and_customer_id_if_provided(directory_client):
    groups = [
        {"id": "test_group_id", "name": "test_group", "email": "email@domain.com"},
        {"id": "test_group_id2", "name": "test_group2", "email": "email2@domain.com"},
    ]
    _set_pages(directory_client.groups, [{"groups": groups}])

    result = google_directory.list_groups(
        delegated_user_email="custom.email@domain.com",
        customer="custom_customer_id",
    )

    assert result == groups
    directory_client.factory.assert_called_once_with(
        scopes=GROUP_READONLY_SCOPES,
        delegated_user_email="custom.email@domain.com",
    )
    directory_client.groups.list.assert_called_once_with(
        customer="custom_customer_id",
        maxResults=200,
        orderBy="email",
    )


def test_list_groups_converts_residual_kwargs_to_camel_case(directory_client):
    _set_pages(directory_client.groups, [{"groups": []}])

    google_directory.list_groups(customer="custom_customer_id", max_results=10)

    assert directory_client.groups.list.call_args.kwargs["maxResults"] == 10


def test_list_groups_concatenates_pages(directory_client):
    _set_pages(
        directory_client.groups,
        [
            {"groups": [{"id": "group1"}], "nextPageToken": "token"},
            {"groups": [{"id": "group2"}]},
        ],
    )

    assert google_directory.list_groups() == [{"id": "group1"}, {"id": "group2"}]


def test_list_groups_propagates_http_error(directory_client):
    error = _http_error(403)
    directory_client.groups.list.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_directory.list_groups()

    assert exc_info.value is error


def test_list_group_members_calls_directory_members_list_with_correct_args(directory_client):
    _set_pages(directory_client.members, [{"members": [{"id": "test_member_id"}]}])

    assert google_directory.list_group_members("test_group_key") == [{"id": "test_member_id"}]

    directory_client.factory.assert_called_once_with(scopes=GROUP_READONLY_SCOPES, delegated_user_email=None)
    directory_client.members.list.assert_called_once_with(
        groupKey="test_group_key",
        maxResults=200,
        fields=None,
    )


def test_list_group_members_uses_custom_delegated_user_email_and_fields_if_provided(directory_client):
    members = [
        {"id": "test_member_id", "email": "member@domain.com"},
        {"id": "test_member_id2", "email": "member2@domain.com"},
    ]
    _set_pages(directory_client.members, [{"members": members}])

    result = google_directory.list_group_members(
        "test_group_key",
        fields="members(email)",
        delegated_user_email="custom.email@domain.com",
    )

    assert result == members
    directory_client.factory.assert_called_once_with(
        scopes=GROUP_READONLY_SCOPES,
        delegated_user_email="custom.email@domain.com",
    )
    directory_client.members.list.assert_called_once_with(
        groupKey="test_group_key",
        maxResults=200,
        fields="members(email)",
    )


def test_list_group_members_concatenates_pages(directory_client):
    _set_pages(
        directory_client.members,
        [
            {"members": [{"id": "member1"}], "nextPageToken": "token"},
            {"members": [{"id": "member2"}]},
        ],
    )

    assert google_directory.list_group_members("test_group_key") == [{"id": "member1"}, {"id": "member2"}]


def test_list_group_members_propagates_http_error(directory_client):
    error = _http_error(404)
    directory_client.members.list.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_directory.list_group_members("test_group_key")

    assert exc_info.value is error


@pytest.mark.parametrize(
    "removed",
    [
        "get_user",
        "get_group",
        "add_users_to_group",
        "convert_google_groups_members_to_dataframe",
    ],
)
def test_removed_directory_functions_are_deleted(removed):
    assert not hasattr(google_directory, removed)


@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members(
    mock_list_groups,
    mock_retry_request,
    mock_list_users,
    google_groups,
    google_group_members,
    google_users,
    google_groups_w_users,
):
    groups = google_groups(2)
    group_members = [[], google_group_members(2)]
    users = google_users(2)
    groups_with_users = google_groups_w_users(2, 2)

    groups_with_users.remove(groups_with_users[0])

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = group_members
    mock_list_users.return_value = users

    assert google_directory.list_groups_with_members() == groups_with_users


@patch("integrations.google_workspace.google_directory.filters.filter_by_condition")
@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_filtered(
    mock_list_groups,
    mock_retry_request,
    mock_list_users,
    mock_filter_by_condition,
    google_groups,
    google_group_members,
    google_users,
    google_groups_w_users,
):
    groups = google_groups(2, prefix="test-")
    groups_to_filter_out = google_groups(4)[2:]
    groups.extend(groups_to_filter_out)
    group_members = [[], google_group_members(2)]
    users = google_users(2)

    groups_with_users = google_groups_w_users(4, 2, group_prefix="test-")[:2]
    groups_with_users.remove(groups_with_users[0])

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = group_members
    mock_list_users.return_value = users
    mock_filter_by_condition.return_value = groups[:2]
    groups_filters = [lambda group: "test-" in group["name"]]

    assert google_directory.list_groups_with_members(groups_filters=groups_filters) == groups_with_users
    mock_filter_by_condition.assert_called_once_with(groups, groups_filters[0])
    assert mock_retry_request.call_count == 2
    assert mock_list_users.call_count == 1


@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_error_in_list_group_members(
    mock_list_groups,
    mock_retry_request,
    mock_list_users,
    google_groups,
    google_group_members,
    google_users,
    google_groups_w_users,
):
    groups = google_groups(2)
    group_members = [Exception("Error fetching group members"), google_group_members(2)]
    users = google_users(2)

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = [
        group_members[0],
        group_members[1],
        users[0],
        users[1],
    ]
    mock_list_users.return_value = users

    # Only the second group should be processed
    expected_groups_with_users = [groups[1]]
    expected_groups_with_users[0]["members"] = group_members[1]
    expected_groups_with_users[0]["members"][0].update(users[0])
    expected_groups_with_users[0]["members"][1].update(users[1])

    assert google_directory.list_groups_with_members() == expected_groups_with_users


@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.get_members_details")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_error_in_get_user(
    mock_list_groups,
    mock_retry_request,
    mock_get_members_details,
    mock_list_users,
    google_groups,
    google_group_members,
    google_users,
):
    groups = google_groups(2)
    group_members = [google_group_members(2), google_group_members(2)]
    users = [
        Exception("Error fetching user details"),
        google_users(2)[1],
        google_users(1)[0],
        google_users(2)[1],
    ]

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = [
        group_members[0],
        group_members[1],
    ]
    mock_get_members_details.side_effect = [
        [],
        group_members[1],
    ]
    mock_list_users.return_value = users

    # Only the second group should be processed
    expected_groups_with_users = [groups[1]]
    expected_groups_with_users[0]["members"] = group_members[1]
    expected_groups_with_users[0]["members"][0].update(users[2])
    expected_groups_with_users[0]["members"][1].update(users[3])

    assert google_directory.list_groups_with_members() == expected_groups_with_users


@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_tolerate_errors(
    mock_list_groups,
    mock_retry_request,
    mock_list_users,
    google_groups_w_users,
):

    groups = [
        {
            "id": "group1",
            "email": "groupEmail1",
            "name": "name1",
            "directMembersCount": 2,
        },
        {
            "id": "group2",
            "email": "groupEmail2",
            "name": "name2",
            "directMembersCount": 2,
        },
    ]

    group_members = [
        [
            {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
            {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        ],
        [
            {"email": "email3", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
            {"email": "email4", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        ],
    ]

    users = [
        # Exception("Error fetching user details"),
        {"id": "user2", "name": "user2", "primaryEmail": "email2"},
        {"id": "user3", "name": "user3", "primaryEmail": "email3"},
        {"id": "user4", "name": "user4", "primaryEmail": "email4"},
    ]

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = [
        group_members[0],
        group_members[1],
    ]

    mock_list_users.return_value = users

    # Expected result should include both groups, with the second group having one member
    expected_groups_with_users = [
        {
            "id": "group1",
            "email": "groupEmail1",
            "name": "name1",
            "directMembersCount": 2,
            "members": [
                {
                    "email": "email1",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                },
                {
                    "email": "email2",
                    "primaryEmail": "email2",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                    "id": "user2",
                    "name": "user2",
                },
            ],
        },
        {
            "id": "group2",
            "email": "groupEmail2",
            "name": "name2",
            "directMembersCount": 2,
            "members": [
                {
                    "email": "email3",
                    "primaryEmail": "email3",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                    "id": "user3",
                    "name": "user3",
                },
                {
                    "email": "email4",
                    "primaryEmail": "email4",
                    "role": "MEMBER",
                    "type": "USER",
                    "status": "ACTIVE",
                    "id": "user4",
                    "name": "user4",
                },
            ],
        },
    ]

    result = google_directory.list_groups_with_members(tolerate_errors=True)

    assert result == expected_groups_with_users


@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_skips_when_no_groups(mock_list_groups):
    mock_list_groups.return_value = []
    assert google_directory.list_groups_with_members() == []


@patch("integrations.google_workspace.google_directory.filters.filter_by_condition")
@patch("integrations.google_workspace.google_directory.list_users")
@patch("integrations.google_workspace.google_directory.retry_request")
@patch("integrations.google_workspace.google_directory.list_groups")
def test_list_groups_with_members_applies_groups_filters(
    mock_list_groups,
    mock_retry_request,
    mock_list_users,
    mock_filter_by_condition,
    google_groups,
    google_group_members,
    google_users,
    google_groups_w_users,
):
    groups = google_groups(2, prefix="test-")
    groups_to_filter_out = google_groups(4)[2:]
    groups.extend(groups_to_filter_out)
    group_members = [[], google_group_members(2)]
    users = google_users(2)

    groups_with_users = google_groups_w_users(4, 2, group_prefix="test-")[:2]
    groups_with_users.remove(groups_with_users[0])

    mock_list_groups.return_value = groups
    mock_retry_request.side_effect = group_members
    mock_list_users.return_value = users
    mock_filter_by_condition.return_value = groups[:2]
    groups_filters = [lambda group: "test-" in group["name"]]

    assert google_directory.list_groups_with_members(groups_filters=groups_filters) == groups_with_users
    mock_filter_by_condition.assert_called_once_with(groups, groups_filters[0])


def test_get_members_details_breaks_on_error():
    members = [
        {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
    ]

    users = [
        {"name": "user2", "primaryEmail": "email2"},
    ]

    result = google_directory.get_members_details(members, users)

    assert result == []


def test_get_members_details_continues_on_tolerate_errors():
    members = [
        {"email": "email1", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
        {"email": "email2", "role": "MEMBER", "type": "USER", "status": "ACTIVE"},
    ]

    users = [
        {"name": "user2", "primaryEmail": "email2"},
    ]

    result = google_directory.get_members_details(members, users, tolerate_errors=True)

    expected_result = [
        members[0],
        {
            "email": "email2",
            "role": "MEMBER",
            "type": "USER",
            "status": "ACTIVE",
            "name": "user2",
            "primaryEmail": "email2",
        },
    ]
    assert result == expected_result
