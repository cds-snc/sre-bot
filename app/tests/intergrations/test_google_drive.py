import os
import pytest

from integrations import google_drive

from unittest.mock import patch


@patch("integrations.google_drive.build")
@patch("integrations.google_drive.pickle")
def test_get_google_service_returns_build_object(pickle_mock, build_mock):
    google_drive.get_google_service("drive", "v3")
    build_mock.assert_called_once_with(
        "drive", "v3", credentials=pickle_mock.loads(os.environ.get("PICKLE_STRING"))
    )


@patch("integrations.google_drive.PICKLE_STRING", False)
def test_get_google_service_raises_exception_if_pickle_string_not_set():
    with pytest.raises(Exception) as e:
        google_drive.get_google_service("drive", "v3")
    assert "Pickle string not set" in str(e.value)


@patch("integrations.google_drive.pickle")
def test_get_google_service_raises_exception_if_pickle_string_is_invalid(pickle_mock):
    pickle_mock.loads.side_effect = Exception("Invalid pickle string")
    with pytest.raises(Exception) as e:
        google_drive.get_google_service("drive", "v3")
    assert "Invalid pickle string" in str(e.value)


@patch("integrations.google_drive.get_google_service")
def test_create_folder_returns_folder_name(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "name": "test_folder"
    }
    assert google_drive.create_folder("test_folder") == "Created folder test_folder"


@patch("integrations.google_drive.get_google_service")
def test_create_new_incident(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.copy.return_value.execute.return_value = {
        "id": "test_incident"
    }
    assert (
        google_drive.create_new_incident("test_incident", "test_folder")
        == "test_incident"
    )


@patch("integrations.google_drive.get_google_service")
def test_list_folders_returns_folder_names(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.list.return_value.execute.return_value = {
        "files": [{"name": "test_folder"}]
    }
    assert google_drive.list_folders() == [{"name": "test_folder"}]


@patch("integrations.google_drive.get_google_service")
def test_merge_data(get_google_service_mock):
    get_google_service_mock.return_value.documents.return_value.batchUpdate.return_value.execute.return_value = (
        True
    )
    assert (
        google_drive.merge_data("file_id", "name", "product", "slack_channel") is True
    )


@patch("integrations.google_drive.get_google_service")
def test_update_incident_list(get_google_service_mock):
    get_google_service_mock.return_value.spreadsheets.return_value.values.return_value.append.return_value.execute.return_value = (
        True
    )
    assert (
        google_drive.update_incident_list(
            "document_link", "name", "slug", "product", "channel_url"
        )
        is True
    )
