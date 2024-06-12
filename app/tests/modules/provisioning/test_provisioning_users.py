from unittest.mock import patch
from modules.provisioning import users


def test_get_users_from_unknown_integration():
    users_list = users.get_users_from_integration("unknown_integration")
    assert users_list == []


@patch("modules.provisioning.users.google_directory")
def test_get_users_from_integration_google(mock_google_directory):
    mock_google_directory.list_users.return_value = ["user1", "user2"]
    users_list = users.get_users_from_integration("google_directory")
    mock_google_directory.list_users.assert_called_once()
    assert users_list == mock_google_directory.list_users.return_value


@patch("modules.provisioning.users.identity_store")
def test_get_users_from_integration_aws(mock_identity_store):
    mock_identity_store.list_users.return_value = ["user1", "user2"]
    users_list = users.get_users_from_integration("aws_identity_center")
    mock_identity_store.list_users.assert_called_once()
    assert users_list == mock_identity_store.list_users.return_value


@patch("modules.provisioning.users.filters")
@patch("modules.provisioning.users.google_directory")
def test_get_users_from_integration_filters_applied(
    mock_google_directory, mock_filters
):
    users_list = ["user1", "user2"]
    mock_google_directory.list_users.return_value = users_list
    mock_filters.filter_by_condition.return_value = ["user1"]
    users_list_filtered = users.get_users_from_integration(
        "google_directory", processing_filters=["filter1"]
    )
    mock_filters.filter_by_condition.assert_called_once_with(users_list, "filter1")
    assert users_list_filtered == ["user1"]
