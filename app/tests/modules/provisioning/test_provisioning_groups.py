from unittest.mock import patch
from modules.provisioning import groups


@patch("modules.provisioning.groups.filter_tools.filter_by_condition")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_with_members_from_integration_google(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filter_tools,
    google_groups_w_users,
):
    google_groups = google_groups_w_users(n_groups=3, n_users=3)
    mock_google_list_groups_with_members.return_value = google_groups

    response = groups.get_groups_with_members_from_integration("google_groups")

    assert response == google_groups

    assert mock_google_list_groups_with_members.called_once_with(
        query=None, members_details=True
    )
    assert not mock_filter_tools.called
    assert not mock_aws_list_groups_with_memberships.called


@patch("modules.provisioning.groups.filter_tools.filter_by_condition")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_with_members_from_integration_google_query(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filter_tools,
    google_groups_w_users,
):
    google_groups = google_groups_w_users(n_groups=3, n_users=3, prefix="aws-")
    google_groups.extend(google_groups_w_users(n_groups=3, n_users=3))
    mock_google_list_groups_with_members.return_value = google_groups[:3]

    query = "email:aws-*"
    response = groups.get_groups_with_members_from_integration(
        "google_groups", query=query
    )

    assert response == google_groups[:3]

    assert mock_google_list_groups_with_members.called_once_with(
        query="email:aws-*", members_details=True
    )
    assert not mock_filter_tools.called
    assert not mock_aws_list_groups_with_memberships.called


@patch("modules.provisioning.groups.filter_tools.filter_by_condition")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_with_members_from_integration_case_aws(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filter_tools,
    aws_groups_w_users,
):
    aws_groups = aws_groups_w_users(n_groups=3, n_users=3)
    mock_aws_list_groups_with_memberships.return_value = aws_groups

    response = groups.get_groups_with_members_from_integration("aws_identity_center")

    assert response == aws_groups

    assert mock_aws_list_groups_with_memberships.called_once_with(members_details=True)
    assert not mock_filter_tools.called
    assert not mock_google_list_groups_with_members.called


@patch("modules.provisioning.groups.filter_tools.filter_by_condition")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_with_members_from_integration_empty_groups(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filter_tools,
):
    google_groups = []
    mock_google_list_groups_with_members.return_value = google_groups

    response = groups.get_groups_with_members_from_integration("google_groups")

    assert response == google_groups

    assert mock_google_list_groups_with_members.called_once_with(
        query=None, members_details=True
    )
    assert not mock_filter_tools.called
    assert not mock_aws_list_groups_with_memberships.called


@patch("modules.provisioning.groups.filter_tools.filter_by_condition")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_with_members_from_integration_case_invalid(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filter_tools,
):
    response = groups.get_groups_with_members_from_integration("invalid_case")

    assert response == []

    assert not mock_filter_tools.called
    assert not mock_aws_list_groups_with_memberships.called
    assert not mock_google_list_groups_with_members.called


@patch("modules.provisioning.groups.filter_tools.filter_by_condition")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_with_members_from_integration_filters_applied(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filter_tools,
    aws_groups_w_users,
):
    aws_groups = []
    aws_groups_prefix = aws_groups_w_users(n_groups=3, n_users=3, prefix="prefix")
    aws_groups.extend(aws_groups_prefix)
    aws_groups_wo_prefix = aws_groups_w_users(n_groups=3, n_users=3)
    aws_groups.extend(aws_groups_wo_prefix)
    mock_aws_list_groups_with_memberships.return_value = aws_groups
    mock_filter_tools.side_effect = [aws_groups_prefix, []]
    filters = [
        lambda group: "prefix" in group["DisplayName"],
        lambda group: "prefix" in group["Description"],
    ]

    response = groups.get_groups_with_members_from_integration(
        "aws_identity_center", filters=filters
    )

    assert response == []

    assert mock_filter_tools.call_count == 2
    assert mock_filter_tools.called_once_with(aws_groups, filters)
    assert mock_filter_tools.called_once_with(aws_groups_prefix, filters)
    assert mock_aws_list_groups_with_memberships.called_once_with(members_details=True)
    assert not mock_google_list_groups_with_members.called


@patch("modules.provisioning.groups.filter_tools.filter_by_condition")
@patch("modules.provisioning.groups.identity_store.list_groups_with_memberships")
@patch("modules.provisioning.groups.google_directory.list_groups_with_members")
def test_get_groups_with_members_from_integration_filters_returns_subset(
    mock_google_list_groups_with_members,
    mock_aws_list_groups_with_memberships,
    mock_filter_tools,
    aws_groups_w_users,
):
    aws_groups = []
    aws_groups_prefix = aws_groups_w_users(n_groups=3, n_users=3, prefix="prefix")
    aws_groups.extend(aws_groups_prefix)
    aws_groups_wo_prefix = aws_groups_w_users(n_groups=3, n_users=3)
    aws_groups.extend(aws_groups_wo_prefix)
    mock_aws_list_groups_with_memberships.return_value = aws_groups
    mock_filter_tools.side_effect = [aws_groups_prefix]
    filters = [
        lambda group: "prefix" in group["DisplayName"],
    ]

    response = groups.get_groups_with_members_from_integration(
        "aws_identity_center", filters=filters
    )

    assert response == aws_groups_prefix

    assert mock_filter_tools.call_count == 1
    assert mock_filter_tools.called_once_with(aws_groups, filters)
    assert mock_filter_tools.called_once_with(aws_groups_prefix, filters)
    assert mock_aws_list_groups_with_memberships.called_once_with(members_details=True)
    assert not mock_google_list_groups_with_members.called


# @patch("modules.provisioning.groups.filter_tools.get_nested_value")
# def test_get_matching_groups_returns_empty_lists(mock_get_nested_value):
#     source_groups = []
#     target_groups = []
#     matching_key = "key"
#     result = groups.get_matching_groups(source_groups, target_groups, matching_key)

#     assert result == ([], [])
#     assert not mock_get_nested_value.called


# @patch("modules.provisioning.groups.filter_tools.get_nested_value")
# def test_get_matching_groups_returns_empty_lists_no_source(mock_get_nested_value):
#     source_groups = []
#     target_groups = [{"key": "value"}]
#     matching_key = "key"
#     mock_get_nested_value.return_value = target_groups
#     result = groups.get_matching_groups(source_groups, target_groups, matching_key)

#     assert result == ([], [])
#     assert not mock_get_nested_value.called


# @patch("modules.provisioning.groups.filter_tools.get_nested_value")
# def test_get_matching_groups_returns_empty_lists_no_target(mock_get_nested_value):
#     source_groups = [{"key": "value"}]
#     target_groups = []
#     matching_key = "key"
#     mock_get_nested_value.return_value = source_groups
#     result = groups.get_matching_groups(source_groups, target_groups, matching_key)

#     assert result == ([], [])
#     assert not mock_get_nested_value.called


# @patch("modules.provisioning.groups.filter_tools.get_nested_value")
# def test_get_matching_groups_returns_empty_lists_key_not_found(mock_get_nested_value):
#     source_groups = [
#         {"wrong_key": "value", "name": "group1", "display_name": "Group 1"}
#     ]
#     target_groups = [
#         {"another_key": "value", "some_value": "value", "another_group_name": "Group 1"}
#     ]
#     matching_key = "key"
#     mock_get_nested_value.side_effect = lambda *args, **kwargs: None
#     result = groups.get_matching_groups(source_groups, target_groups, matching_key)

#     assert result == ([], [])
#     assert mock_get_nested_value.call_count == 2


# @patch("modules.provisioning.groups.filter_tools.get_nested_value")
# def test_get_matching_groups_returns_list_with_simple_dicts(mock_get_nested_value):
#     source_groups = [{"key": "value", "name": "group1", "display_name": "Group 1"}]
#     target_groups = [
#         {"key": "value", "some_value": "value", "another_group_name": "Group 1"}
#     ]
#     matching_key = "key"
#     mock_get_nested_value.side_effect = lambda *args, **kwargs: "value"
#     result = groups.get_matching_groups(source_groups, target_groups, matching_key)

#     assert result == (source_groups, target_groups)
#     assert mock_get_nested_value.call_count == 2


# @patch("modules.provisioning.groups.filter_tools.get_nested_value")
# def test_get_matching_groups_returns_list_with_nested_dicts(mock_get_nested_value):
#     source_groups = [
#         {
#             "key": "value",
#             "name": "group1",
#             "display_name": "Group 1",
#             "nested": {"key": "value"},
#         }
#     ]
#     target_groups = [
#         {
#             "key": "value",
#             "some_value": "value",
#             "another_group_name": "Group 1",
#             "nested": {"key": "value"},
#         }
#     ]
#     matching_key = "nested.key"
#     mock_get_nested_value.side_effect = lambda *args, **kwargs: "value"
#     result = groups.get_matching_groups(source_groups, target_groups, matching_key)

#     assert result == (source_groups, target_groups)
#     assert mock_get_nested_value.call_count == 2


# @patch("modules.provisioning.groups.filter_tools.get_nested_value")
# def test_get_matching_groups_returns_list_with_different_groups(mock_get_nested_value):
#     source_groups = [
#         {
#             "key": "value",
#             "name": "group1",
#             "display_name": "Group 1",
#             "nested": {"key": "value"},
#         },
#         {
#             "key": "value",
#             "name": "group2",
#             "display_name": "Group 2",
#             "nested": {"key": "different_value"},
#         },
#     ]
#     target_groups = [
#         {
#             "key": "value",
#             "some_value": "value",
#             "another_group_name": "Group 1",
#             "nested": {"key": "not_matching_value"},
#         },
#         {
#             "key": "value",
#             "some_value": "value",
#             "another_group_name": "Group 2",
#             "nested": {"key": "value"},
#         },
#     ]
#     matching_key = "nested.key"
#     mock_get_nested_value.side_effect = [
#         "value",
#         "different_value",
#         "not_matching_value",
#         "value",
#     ]
#     result = groups.get_matching_groups(source_groups, target_groups, matching_key)

#     assert result == ([source_groups[0]], [target_groups[1]])
#     assert mock_get_nested_value.call_count == 4
