from unittest.mock import patch, call
from modules.provisioning import groups


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_from_integration_google(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filters,
    google_groups_w_users,
):
    google_groups = google_groups_w_users(n_groups=3, n_users=3)
    mock_google_list_groups_with_members.return_value = google_groups

    response = groups.get_groups_from_integration("google_groups")

    assert response == google_groups

    assert mock_google_list_groups_with_members.called_once_with(
        query=None, members_details=True
    )
    assert not mock_filters.filter_by_condition.called
    assert not mock_aws_list_groups_with_memberships.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_from_integration_google_query(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filters,
    google_groups_w_users,
):
    google_groups = google_groups_w_users(n_groups=3, n_users=3, group_prefix="aws-")
    google_groups.extend(google_groups_w_users(n_groups=3, n_users=3))
    mock_google_list_groups_with_members.return_value = google_groups[:3]

    query = "email:aws-*"
    response = groups.get_groups_from_integration("google_groups", query=query)

    assert response == google_groups[:3]

    assert mock_google_list_groups_with_members.called_once_with(
        query="email:aws-*", members_details=True
    )
    assert not mock_filters.filter_by_condition.called
    assert not mock_aws_list_groups_with_memberships.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_from_integration_case_aws(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filters,
    aws_groups_w_users,
):
    aws_groups = aws_groups_w_users(n_groups=3, n_users=3)
    mock_aws_list_groups_with_memberships.return_value = aws_groups

    response = groups.get_groups_from_integration("aws_identity_center")

    assert response == aws_groups

    assert mock_aws_list_groups_with_memberships.called_once_with(members_details=True)
    assert not mock_filters.filter_by_condition.called
    assert not mock_google_list_groups_with_members.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_from_integration_empty_groups(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filters,
):
    google_groups = []
    mock_google_list_groups_with_members.return_value = google_groups

    response = groups.get_groups_from_integration("google_groups")

    assert response == google_groups

    assert mock_google_list_groups_with_members.called_once_with(
        query=None, members_details=True
    )
    assert not mock_filters.filter_by_condition.called
    assert not mock_aws_list_groups_with_memberships.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_from_integration_case_invalid(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filters,
):
    response = groups.get_groups_from_integration("invalid_case")

    assert response == []

    assert not mock_filters.filter_by_condition.called
    assert not mock_aws_list_groups_with_memberships.called
    assert not mock_google_list_groups_with_members.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_from_integration_filters_applied(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filters,
    aws_groups_w_users,
):
    aws_groups = []
    aws_groups_prefix = aws_groups_w_users(n_groups=3, n_users=3, group_prefix="prefix")
    aws_groups.extend(aws_groups_prefix)
    aws_groups_wo_prefix = aws_groups_w_users(n_groups=3, n_users=3)
    aws_groups.extend(aws_groups_wo_prefix)
    mock_aws_list_groups_with_memberships.return_value = aws_groups
    mock_filters.filter_by_condition.side_effect = [aws_groups_prefix, []]
    post_processing_filters = [
        lambda group: "prefix" in group["DisplayName"],
        lambda group: "prefix" in group["Description"],
    ]

    response = groups.get_groups_from_integration(
        "aws_identity_center", post_processing_filters=post_processing_filters
    )

    assert response == []

    assert mock_filters.filter_by_condition.call_count == 2
    assert mock_filters.filter_by_condition.called_once_with(
        aws_groups, post_processing_filters
    )
    assert mock_filters.filter_by_condition.called_once_with(
        aws_groups_prefix, post_processing_filters
    )
    assert mock_aws_list_groups_with_memberships.called_once_with(members_details=True)
    assert not mock_google_list_groups_with_members.called


@patch("modules.provisioning.groups.filters")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_from_integration_filters_returns_subset(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filters,
    aws_groups_w_users,
):
    aws_groups = []
    aws_groups_prefix = aws_groups_w_users(n_groups=3, n_users=3, group_prefix="prefix")
    aws_groups.extend(aws_groups_prefix)
    aws_groups_wo_prefix = aws_groups_w_users(n_groups=3, n_users=3)
    aws_groups.extend(aws_groups_wo_prefix)
    mock_aws_list_groups_with_memberships.return_value = aws_groups
    mock_filters.filter_by_condition.side_effect = [aws_groups_prefix]
    post_processing_filters = [
        lambda group: "prefix" in group["DisplayName"],
    ]

    response = groups.get_groups_from_integration(
        "aws_identity_center", post_processing_filters=post_processing_filters
    )

    assert response == aws_groups_prefix

    assert mock_filters.filter_by_condition.call_count == 1
    assert mock_filters.filter_by_condition.called_once_with(
        aws_groups, post_processing_filters
    )
    assert mock_filters.filter_by_condition.called_once_with(
        aws_groups_prefix, post_processing_filters
    )
    assert mock_aws_list_groups_with_memberships.called_once_with(members_details=True)
    assert not mock_google_list_groups_with_members.called


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
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
        call("log_groups_summary", integration_name="AWS", groups_count=3),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="group-name1",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name1",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name1",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name1",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="group-name2",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name2",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name2",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name2",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="group-name3",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name3",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name3",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name3",
            member_name="user-email3@test.com",
        ),
    ]
    mock_logger.info.assert_has_calls(expected_info_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_no_groups(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
    groups_w_members = []
    groups.log_groups(
        groups_w_members,
        group_display_key="DisplayName",
        members="GroupMemberships",
        members_display_key="MemberId.UserName",
        integration_name="AWS",
    )
    expected_info_messages = [
        call("log_groups_summary", integration_name="AWS", groups_count=0)
    ]
    mock_logger.info.assert_has_calls(expected_info_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_missing_members_key(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
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
        call("log_groups_summary", integration_name="AWS", groups_count=3),
        call("log_group_no_members", integration_name="AWS", group_name="group-name1"),
        call("log_group_no_members", integration_name="AWS", group_name="group-name2"),
        call("log_group_no_members", integration_name="AWS", group_name="group-name3"),
    ]
    expected_warn_messages = [
        call(
            "log_groups_missing_members_key",
            integration_name="AWS",
            missing_key="members",
        )
    ]
    mock_logger.info.assert_has_calls(expected_info_messages)
    mock_logger.warning.assert_has_calls(expected_warn_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_missing_group_display_key(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
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
        call("log_groups_summary", integration_name="AWS", groups_count=3),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="<Group Name not found>",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="<Group Name not found>",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email3@test.com",
        ),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="<Group Name not found>",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email1@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email2@test.com",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="<Group Name not found>",
            member_name="user-email3@test.com",
        ),
    ]

    expected_warn_messages = [
        call(
            "log_groups_missing_display_key",
            integration_name="AWS",
            missing_key="group_display_key",
        )
    ]

    mock_logger.info.assert_has_calls(expected_info_messages)
    mock_logger.warning.assert_has_calls(expected_warn_messages)


@patch("modules.provisioning.groups.logger")
@patch("modules.provisioning.groups.filters")
def test_log_groups_no_group_members_display_keys(
    mock_filters,
    mock_logger,
    aws_groups_w_users,
):
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
        call("log_groups_summary", integration_name="AWS", groups_count=3),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="group-name1",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name1",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name1",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name1",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="group-name2",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name2",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name2",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name2",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_members",
            integration_name="AWS",
            group_name="group-name3",
            members_count=3,
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name3",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name3",
            member_name="<User Name not found>",
        ),
        call(
            "log_group_member",
            integration_name="AWS",
            group_name="group-name3",
            member_name="<User Name not found>",
        ),
    ]

    expected_warn_messages = [
        call(
            "log_groups_missing_display_key",
            integration_name="AWS",
            missing_key="members_display_key",
        )
    ]

    mock_logger.info.assert_has_calls(expected_info_messages)
    mock_logger.warning.assert_has_calls(expected_warn_messages)
