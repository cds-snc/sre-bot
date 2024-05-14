from unittest.mock import patch
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
    processing_filters = [
        lambda group: "prefix" in group["DisplayName"],
        lambda group: "prefix" in group["Description"],
    ]

    response = groups.get_groups_from_integration(
        "aws_identity_center", processing_filters=processing_filters
    )

    assert response == []

    assert mock_filters.filter_by_condition.call_count == 2
    assert mock_filters.filter_by_condition.called_once_with(aws_groups, processing_filters)
    assert mock_filters.filter_by_condition.called_once_with(aws_groups_prefix, processing_filters)
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
    processing_filters = [
        lambda group: "prefix" in group["DisplayName"],
    ]

    response = groups.get_groups_from_integration(
        "aws_identity_center", processing_filters=processing_filters
    )

    assert response == aws_groups_prefix

    assert mock_filters.filter_by_condition.call_count == 1
    assert mock_filters.filter_by_condition.called_once_with(aws_groups, processing_filters)
    assert mock_filters.filter_by_condition.called_once_with(aws_groups_prefix, processing_filters)
    assert mock_aws_list_groups_with_memberships.called_once_with(members_details=True)
    assert not mock_google_list_groups_with_members.called
