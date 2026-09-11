from unittest.mock import MagicMock, call, patch

import pytest

from infrastructure.directory.models import (
    DirectoryGroup,
    DirectoryGroupFailure,
    DirectoryGroupsWithMembers,
    DirectoryGroupWithMembers,
    DirectoryMember,
    DirectoryUser,
)
from infrastructure.operations import OperationResult, OperationStatus
from modules.provisioning import groups, users


class FakeDirectoryProvider:
    """Fake provider that records list_groups_with_members calls."""

    def __init__(self, result: OperationResult[DirectoryGroupsWithMembers]):
        self._result = result
        self.calls: list[dict] = []

    def list_groups_with_members(self, *args, **kwargs) -> OperationResult[DirectoryGroupsWithMembers]:
        self.calls.append({"args": args, "kwargs": kwargs})
        return self._result


class LegacyGoogleDirectoryStub:
    """Legacy seam stub used to assert the old boundary is not called."""

    def __init__(self, groups_with_members: list[dict] | None = None):
        self.groups_with_members = groups_with_members or []
        self.calls: list[dict] = []

    def list_groups_with_members(self, groups_filters=None, query=None):
        self.calls.append({"groups_filters": groups_filters, "query": query})
        return self.groups_with_members


def _directory_group_with_members(
    group_email: str,
    group_name: str,
    member_emails: tuple[str, ...],
) -> DirectoryGroupWithMembers:
    group = DirectoryGroup(
        group_email=group_email,
        group_slug=group_email.split("@")[0],
        provider_group_id=f"group-{group_email}",
        name=group_name,
    )
    members = tuple(DirectoryMember(email=email, provider_user_id=f"user-{email}") for email in member_emails)
    return DirectoryGroupWithMembers(group=group, members=members)


def _directory_user(email: str, given_name: str, family_name: str) -> DirectoryUser:
    return DirectoryUser(
        email=email,
        provider_user_id=f"user-{email}",
        given_name=given_name,
        family_name=family_name,
    )


def _bind_google_branch(
    monkeypatch: pytest.MonkeyPatch,
    provider_result: OperationResult[DirectoryGroupsWithMembers],
    directory_users: list[DirectoryUser] | None = None,
):
    provider = FakeDirectoryProvider(provider_result)
    legacy_google = LegacyGoogleDirectoryStub()
    users_calls: list[str] = []

    def _list_users(integration_source: str, **kwargs):
        users_calls.append(integration_source)
        return directory_users or []

    monkeypatch.setattr(groups, "get_directory_provider", lambda: provider, raising=False)
    monkeypatch.setattr(groups, "google_directory", legacy_google, raising=False)
    monkeypatch.setattr(users, "get_users_from_integration", _list_users, raising=False)

    return provider, legacy_google, users_calls


def _warning_contains(mock_logger, **expected) -> bool:
    return any(all(call.kwargs.get(key) == value for key, value in expected.items()) for call in mock_logger.call_args_list)


def test_get_groups_from_integration_google_uses_directory_provider_and_returns_legacy_shape(monkeypatch):
    provider_result = OperationResult.success(
        DirectoryGroupsWithMembers(
            groups=(
                _directory_group_with_members("aws-dev@example.com", "AWS-Developers", ("u1@example.com",)),
                _directory_group_with_members("aws-ops@example.com", "AWS-Ops", ("u2@example.com",)),
            )
        )
    )
    directory_users = [
        _directory_user("u1@example.com", "User", "One"),
        _directory_user("u2@example.com", "User", "Two"),
    ]
    provider, legacy_google, users_calls = _bind_google_branch(monkeypatch, provider_result, directory_users)

    response = groups.get_groups_from_integration("google_groups")

    assert response == [
        {
            "email": "aws-dev@example.com",
            "name": "AWS-Developers",
            "members": [
                {
                    "primaryEmail": "u1@example.com",
                    "email": "u1@example.com",
                    "name": {"givenName": "User", "familyName": "One"},
                }
            ],
        },
        {
            "email": "aws-ops@example.com",
            "name": "AWS-Ops",
            "members": [
                {
                    "primaryEmail": "u2@example.com",
                    "email": "u2@example.com",
                    "name": {"givenName": "User", "familyName": "Two"},
                }
            ],
        },
    ]
    assert provider.calls == [{"args": (), "kwargs": {"query": ""}}]
    assert users_calls == ["google_directory"]
    assert legacy_google.calls == []


def test_get_groups_from_integration_google_forwards_query(monkeypatch):
    provider_result = OperationResult.success(
        DirectoryGroupsWithMembers(groups=(_directory_group_with_members("aws-dev@example.com", "AWS-Developers", ()),))
    )
    provider, legacy_google, users_calls = _bind_google_branch(monkeypatch, provider_result, [])

    groups.get_groups_from_integration("google_groups", query="email:aws-*")

    assert provider.calls == [{"args": (), "kwargs": {"query": "email:aws-*"}}]
    assert users_calls == ["google_directory"]
    assert legacy_google.calls == []


@patch("modules.provisioning.groups.logger")
def test_get_groups_from_integration_google_logs_and_skips_group_failures(mock_logger, monkeypatch):
    provider_result = OperationResult.success(
        DirectoryGroupsWithMembers(
            groups=(_directory_group_with_members("aws-dev@example.com", "AWS-Developers", ("u1@example.com",)),),
            failures=(
                DirectoryGroupFailure(
                    group_email="aws-failed@example.com",
                    status=OperationStatus.TRANSIENT_ERROR,
                    error_code="quotaExceeded",
                    message="Quota exceeded while listing members",
                ),
            ),
        )
    )
    provider, legacy_google, _ = _bind_google_branch(
        monkeypatch,
        provider_result,
        [_directory_user("u1@example.com", "User", "One")],
    )
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger

    response = groups.get_groups_from_integration("google_groups")

    assert response == [
        {
            "email": "aws-dev@example.com",
            "name": "AWS-Developers",
            "members": [
                {
                    "primaryEmail": "u1@example.com",
                    "email": "u1@example.com",
                    "name": {"givenName": "User", "familyName": "One"},
                }
            ],
        }
    ]
    assert _warning_contains(
        bound_logger.warning,
        group_email="aws-failed@example.com",
        error_code="quotaExceeded",
    )
    assert provider.calls == [{"args": (), "kwargs": {"query": ""}}]
    assert legacy_google.calls == []


@patch("modules.provisioning.groups.logger")
def test_get_groups_from_integration_google_drops_groups_with_no_resolvable_members(mock_logger, monkeypatch):
    provider_result = OperationResult.success(
        DirectoryGroupsWithMembers(
            groups=(
                _directory_group_with_members("aws-dev@example.com", "AWS-Developers", ("u1@example.com",)),
                _directory_group_with_members("aws-empty@example.com", "AWS-Empty", ("unknown@example.com",)),
            )
        )
    )
    provider, legacy_google, _ = _bind_google_branch(
        monkeypatch,
        provider_result,
        [_directory_user("u1@example.com", "User", "One")],
    )
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger

    response = groups.get_groups_from_integration("google_groups")

    assert response == [
        {
            "email": "aws-dev@example.com",
            "name": "AWS-Developers",
            "members": [
                {
                    "primaryEmail": "u1@example.com",
                    "email": "u1@example.com",
                    "name": {"givenName": "User", "familyName": "One"},
                }
            ],
        }
    ]
    assert _warning_contains(bound_logger.warning, group_email="aws-empty@example.com", member_email="unknown@example.com")
    assert provider.calls == [{"args": (), "kwargs": {"query": ""}}]
    assert legacy_google.calls == []


def test_get_groups_from_integration_google_applies_pre_and_post_filters(monkeypatch):
    provider_result = OperationResult.success(
        DirectoryGroupsWithMembers(
            groups=(
                _directory_group_with_members("aws-dev@example.com", "AWS-Developers", ("u1@example.com",)),
                _directory_group_with_members("eng@example.com", "Engineering", ("u1@example.com",)),
            )
        )
    )
    provider, legacy_google, _ = _bind_google_branch(
        monkeypatch,
        provider_result,
        [_directory_user("u1@example.com", "User", "One")],
    )
    filter_inputs: list[list[dict]] = []

    def _filter_by_condition(items: list[dict], predicate):
        filter_inputs.append(items)
        return [item for item in items if predicate(item)]

    monkeypatch.setattr(groups.filters, "filter_by_condition", _filter_by_condition)

    response = groups.get_groups_from_integration(
        "google_groups",
        pre_processing_filters=[lambda group: group["name"].startswith("AWS-")],
        post_processing_filters=[lambda group: group["email"].endswith("@example.com")],
    )

    assert response == [
        {
            "email": "aws-dev@example.com",
            "name": "AWS-Developers",
            "members": [
                {
                    "primaryEmail": "u1@example.com",
                    "email": "u1@example.com",
                    "name": {"givenName": "User", "familyName": "One"},
                }
            ],
        }
    ]
    assert len(filter_inputs) == 2
    assert provider.calls == [{"args": (), "kwargs": {"query": ""}}]
    assert legacy_google.calls == []


def test_get_groups_from_integration_google_propagates_directory_user_failures(monkeypatch):
    provider_result = OperationResult.success(
        DirectoryGroupsWithMembers(
            groups=(_directory_group_with_members("aws-dev@example.com", "AWS-Developers", ("u1@example.com",)),)
        )
    )
    provider = FakeDirectoryProvider(provider_result)
    legacy_google = LegacyGoogleDirectoryStub()

    monkeypatch.setattr(groups, "get_directory_provider", lambda: provider, raising=False)
    monkeypatch.setattr(groups, "google_directory", legacy_google, raising=False)

    def _raise(*args, **kwargs):
        raise users.DirectoryUsersUnavailableError("Directory users unavailable", "quotaExceeded")

    monkeypatch.setattr(users, "get_users_from_integration", _raise, raising=False)

    with pytest.raises(users.DirectoryUsersUnavailableError) as excinfo:
        groups.get_groups_from_integration("google_groups")

    assert excinfo.value.error_code == "quotaExceeded"
    assert provider.calls == [{"args": (), "kwargs": {"query": ""}}]
    assert legacy_google.calls == []


def test_get_groups_from_integration_google_raises_module_local_error_when_provider_fails(monkeypatch):
    provider_result = OperationResult.error(
        status=OperationStatus.TRANSIENT_ERROR,
        message="Directory unavailable",
        error_code="quotaExceeded",
    )
    provider, legacy_google, _ = _bind_google_branch(monkeypatch, provider_result, [])

    with pytest.raises(Exception) as excinfo:
        groups.get_groups_from_integration("google_groups")

    assert type(excinfo.value).__name__ == "DirectoryGroupsUnavailableError"
    assert getattr(excinfo.value, "error_code", None) == "quotaExceeded"
    assert provider.calls == [{"args": (), "kwargs": {"query": ""}}]
    assert legacy_google.calls == []


def test_get_groups_from_integration_google_returns_empty_list_when_provider_has_no_groups(monkeypatch):
    provider_result = OperationResult.success(DirectoryGroupsWithMembers(groups=()))
    provider, legacy_google, users_calls = _bind_google_branch(monkeypatch, provider_result, [])

    response = groups.get_groups_from_integration("google_groups")

    assert response == []
    assert provider.calls == [{"args": (), "kwargs": {"query": ""}}]
    assert users_calls == ["google_directory"]
    assert legacy_google.calls == []


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.build_identity_center_adapter")
def test_get_groups_from_integration_case_aws(
    mock_build,
    mock_filters,
    aws_groups_w_users,
):
    """Successful adapter result with groups and memberships is returned unchanged."""
    aws_groups = aws_groups_w_users(n_groups=3, n_users=3)
    mock_build.return_value.list_groups_with_memberships.return_value = OperationResult.success(data=aws_groups)

    response = groups.get_groups_from_integration("aws_identity_center")

    assert response == aws_groups

    mock_build.return_value.list_groups_with_memberships.assert_called_once_with(groups_filters=[])
    assert not mock_filters.filter_by_condition.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.build_identity_center_adapter")
def test_get_groups_from_integration_case_aws_raises_directory_groups_unavailable_on_failed_listing(
    mock_build,
    mock_filters,
):
    """Failed adapter listing (non-success status) raises module-local error
    carrying message and error_code for structured error handling.
    """
    mock_build.return_value.list_groups_with_memberships.return_value = OperationResult.error(
        status=OperationStatus.TRANSIENT_ERROR,
        message="Identity Store service unavailable",
        error_code="quotaExceeded",
    )

    with pytest.raises(groups.DirectoryGroupsUnavailableError) as excinfo:
        groups.get_groups_from_integration("aws_identity_center")

    assert excinfo.value.error_code == "quotaExceeded"
    assert "unavailable" in str(excinfo.value)


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.build_identity_center_adapter")
def test_get_groups_from_integration_case_aws_empty_listing_returns_empty_list(
    mock_build,
    mock_filters,
):
    """Successful adapter result with no groups yields empty list without raising."""
    mock_build.return_value.list_groups_with_memberships.return_value = OperationResult.success(data=[])

    response = groups.get_groups_from_integration("aws_identity_center")

    assert response == []

    mock_build.return_value.list_groups_with_memberships.assert_called_once_with(groups_filters=[])
    assert not mock_filters.filter_by_condition.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.build_identity_center_adapter")
def test_get_groups_from_integration_case_invalid(
    mock_build,
    mock_filters,
):
    response = groups.get_groups_from_integration("invalid_case")

    assert response == []

    assert not mock_filters.filter_by_condition.called
    assert not mock_build.return_value.list_groups_with_memberships.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.build_identity_center_adapter")
def test_get_groups_from_integration_filters_applied(
    mock_build,
    mock_filters,
    aws_groups_w_users,
):
    aws_groups = []
    aws_groups_prefix = aws_groups_w_users(n_groups=3, n_users=3, group_prefix="prefix")
    aws_groups.extend(aws_groups_prefix)
    aws_groups_wo_prefix = aws_groups_w_users(n_groups=3, n_users=3)
    aws_groups.extend(aws_groups_wo_prefix)
    mock_build.return_value.list_groups_with_memberships.return_value = OperationResult.success(data=aws_groups)
    mock_filters.filter_by_condition.side_effect = [aws_groups_prefix, []]
    post_processing_filters = [
        lambda group: "prefix" in group["DisplayName"],
        lambda group: "prefix" in group["Description"],
    ]

    response = groups.get_groups_from_integration("aws_identity_center", post_processing_filters=post_processing_filters)

    assert response == []

    mock_filters.filter_by_condition.assert_has_calls(
        [
            call(aws_groups, post_processing_filters[0]),
            call(aws_groups_prefix, post_processing_filters[1]),
        ]
    )
    mock_build.return_value.list_groups_with_memberships.assert_called_once_with(groups_filters=[])


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.build_identity_center_adapter")
def test_get_groups_from_integration_filters_returns_subset(
    mock_build,
    mock_filters,
    aws_groups_w_users,
):
    aws_groups = []
    aws_groups_prefix = aws_groups_w_users(n_groups=3, n_users=3, group_prefix="prefix")
    aws_groups.extend(aws_groups_prefix)
    aws_groups_wo_prefix = aws_groups_w_users(n_groups=3, n_users=3)
    aws_groups.extend(aws_groups_wo_prefix)
    mock_build.return_value.list_groups_with_memberships.return_value = OperationResult.success(data=aws_groups)
    mock_filters.filter_by_condition.side_effect = [aws_groups_prefix]
    post_processing_filters = [
        lambda group: "prefix" in group["DisplayName"],
    ]

    response = groups.get_groups_from_integration("aws_identity_center", post_processing_filters=post_processing_filters)

    assert response == aws_groups_prefix

    assert mock_filters.filter_by_condition.call_count == 1
    mock_filters.filter_by_condition.assert_called_once_with(aws_groups, post_processing_filters[0])

    mock_build.return_value.list_groups_with_memberships.assert_called_once_with(groups_filters=[])


def test_get_groups_from_integration_rejects_return_dataframe():
    with pytest.raises(TypeError):
        groups.get_groups_from_integration("google_groups", return_dataframe=True)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger
    groups_w_members = aws_groups_w_users(3, 3)
    mock_filters.get_nested_value.side_effect = [
        "group-name1",
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        "group-name2",
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        "group-name3",
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]
    groups.log_groups(
        groups_w_members,
        group_display_key="DisplayName",
        members="GroupMemberships",
        members_display_key="MemberId.UserName",
        integration_name="AWS",
    )
    expected_info_messages = [
        call("log_groups_summary", groups_count=3),
        call(
            "log_group_members",
            group_name="group-name1",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="group-name1",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            group_name="group-name1",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            group_name="group-name1",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            group_name="group-name2",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="group-name2",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            group_name="group-name2",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            group_name="group-name2",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            group_name="group-name3",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="group-name3",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            group_name="group-name3",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            group_name="group-name3",
            member_name="user-email3@test.com",
        ),
    ]
    bound_logger.info.assert_has_calls(expected_info_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_no_groups(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger
    groups_w_members = []
    groups.log_groups(
        groups_w_members,
        group_display_key="DisplayName",
        members="GroupMemberships",
        members_display_key="MemberId.UserName",
        integration_name="AWS",
    )
    expected_info_messages = [call("log_groups_summary", groups_count=0)]
    bound_logger.info.assert_has_calls(expected_info_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_missing_members_key(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger
    groups_w_members = aws_groups_w_users(3, 3)
    mock_filters.get_nested_value.side_effect = [
        "group-name1",
        "group-name2",
        "group-name3",
    ]

    groups.log_groups(
        groups_w_members,
        group_display_key="DisplayName",
        members=None,
        members_display_key="MemberId.UserName",
        integration_name="AWS",
    )
    expected_info_messages = [
        call("log_groups_summary", groups_count=3),
        call("log_group_no_members", group_name="group-name1"),
        call("log_group_no_members", group_name="group-name2"),
        call("log_group_no_members", group_name="group-name3"),
    ]
    expected_warn_messages = [
        call(
            "log_groups_missing_members_key",
            missing_key="members",
        )
    ]
    bound_logger.info.assert_has_calls(expected_info_messages)
    bound_logger.warning.assert_has_calls(expected_warn_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_missing_group_display_key(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger
    groups_w_members = aws_groups_w_users(3, 3)
    mock_filters.get_nested_value.side_effect = [
        None,
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        None,
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
        None,
        "user-email1@test.com",
        "user-email2@test.com",
        "user-email3@test.com",
    ]
    groups.log_groups(
        groups_w_members,
        group_display_key=None,
        members="GroupMemberships",
        members_display_key="MemberId.UserName",
        integration_name="AWS",
    )
    expected_info_messages = [
        call("log_groups_summary", groups_count=3),
        call(
            "log_group_members",
            group_name="<Group Name not found>",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            group_name="<Group Name not found>",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            group_name="<Group Name not found>",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            group_name="<Group Name not found>",
            member_name="user-email3@test.com",
        ),
    ]

    expected_warn_messages = [
        call(
            "log_groups_missing_display_key",
            missing_key="group_display_key",
        )
    ]

    bound_logger.info.assert_has_calls(expected_info_messages)
    bound_logger.warning.assert_has_calls(expected_warn_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_no_group_members_display_keys(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
    bound_logger = MagicMock()
    mock_logger.bind.return_value = bound_logger
    groups_w_members = aws_groups_w_users(3, 3)
    mock_filters.get_nested_value.side_effect = [
        "group-name1",
        None,
        None,
        None,
        "group-name2",
        None,
        None,
        None,
        "group-name3",
        None,
        None,
        None,
    ]
    groups.log_groups(
        groups_w_members,
        group_display_key="DisplayName",
        members="GroupMemberships",
        members_display_key=None,
        integration_name="AWS",
    )
    expected_info_messages = [
        call("log_groups_summary", groups_count=3),
        call(
            "log_group_members",
            group_name="group-name1",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="group-name1",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            group_name="group-name1",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            group_name="group-name1",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_members",
            group_name="group-name2",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="group-name2",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            group_name="group-name2",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            group_name="group-name2",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_members",
            group_name="group-name3",
            members_count=3,
        ),
        call(
            "log_group_member",
            group_name="group-name3",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            group_name="group-name3",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            group_name="group-name3",
            member_name="<User Name not found>",
        ),
    ]

    expected_warn_messages = [
        call(
            "log_groups_missing_display_key",
            missing_key="members_display_key",
        )
    ]

    bound_logger.info.assert_has_calls(expected_info_messages)
    bound_logger.warning.assert_has_calls(expected_warn_messages)
