"""Unit tests for google_drive module."""
from unittest.mock import patch, MagicMock

import integrations.google_workspace.google_drive as google_drive


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_add_metadata_returns_result(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.update.return_value.execute.return_value = {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }
    result = google_drive.add_metadata("file_id", "key", "value")
    assert result == {"name": "test_folder", "appProperties": {"key": "value"}}


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_delete_metadata_returns_result(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.update.return_value.execute.return_value = {
        "name": "test_folder",
        "appProperties": {},
    }
    result = google_drive.delete_metadata("file_id", "key")
    get_google_service_mock.return_value.files.return_value.update.assert_called_once_with(
        fileId="file_id",
        body={"appProperties": {"key": None}},
        fields="name, appProperties",
        supportsAllDrives=True,
    )
    assert result == {"name": "test_folder", "appProperties": {}}


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_list_metadata_returns_result(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.get.return_value.execute.return_value = {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }
    assert google_drive.list_metadata("file_id") == {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_create_folder_returns_folder_id(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "test_folder_id"
    }
    assert (
        google_drive.create_folder("test_folder", "parent_folder") == "test_folder_id"
    )


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_create_file_with_valid_type_returns_file_id(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "test_document_id"
    }
    result = google_drive.create_file("test_document", "folder_id", "document")
    assert result == "test_document_id"


@patch("logging.error")
@patch("integrations.google_workspace.google_drive.get_google_service")
def test_create_file_with_invalid_type_raises_value_error(
    get_google_service_mock, mocked_logging_error
):
    result = google_drive.create_file("name", "folder", "invalid_file_type")

    assert result is None
    mocked_logging_error.assert_called_once_with(
        "A ValueError occurred in function 'create_file': Invalid file_type: invalid_file_type"
    )


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_create_file_from_template_returns_file_id(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.copy.return_value.execute.return_value = {
        "id": "test_document_id"
    }
    result = google_drive.create_file_from_template(
        "test_document", "folder_id", "template_id"
    )
    assert result == "test_document_id"


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_get_file_by_name_returns_object(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.list.return_value.execute.return_value = {
        "files": [
            {
                "name": "test_document",
                "id": "test_document_id",
                "appProperties": {},
            },
        ]
    }
    assert google_drive.get_file_by_name("test_file_name", "folder_id") == [
        {
            "name": "test_document",
            "id": "test_document_id",
            "appProperties": {},
        }
    ]


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_copy_file_to_folder_returns_file_id(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.copy.return_value.execute.return_value = {
        "id": "file_id"
    }
    get_google_service_mock.return_value.files.return_value.update.return_value.execute.return_value = {
        "id": "updated_file_id"
    }
    assert (
        google_drive.copy_file_to_folder(
            "file_id", "name", "parent_folder", "destination_folder"
        )
        == "updated_file_id"
    )


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_list_folders_in_folder_returns_folders(get_google_service_mock):
    # Mock the first page of results
    first_page = {
        "files": [
            {"id": "test_folder_id", "name": "test_folder"},
        ],
        "nextPageToken": "token",
    }

    # Mock the second page of results
    second_page = {
        "files": [
            {"id": "test_folder_id2", "name": "test_folder2"},
        ]
    }

    # Mock the list method to return the first page of results
    list_mock = MagicMock()
    list_mock.execute.return_value = first_page
    get_google_service_mock.return_value.files.return_value.list.return_value = (
        list_mock
    )

    # Mock the list_next method to return a new request that returns the second page of results the first time it's called,
    # and None the second time it's called
    second_page_request = MagicMock()
    second_page_request.execute.return_value = second_page
    list_next_mock = MagicMock(side_effect=[second_page_request, None])
    get_google_service_mock.return_value.files.return_value.list_next = list_next_mock

    assert google_drive.list_folders_in_folder("parent_folder") == [
        {"id": "test_folder_id", "name": "test_folder"},
        {"id": "test_folder_id2", "name": "test_folder2"},
    ]


@patch("integrations.google_workspace.google_drive.list_metadata")
def test_healthcheck_healthy(list_metadata_mock):
    list_metadata_mock.return_value = {"id": "test_doc"}
    assert google_drive.healthcheck() is True


@patch("integrations.google_workspace.google_drive.list_metadata")
def test_healthcheck_unhealthy(list_metadata_mock):
    list_metadata_mock.return_value = None
    assert google_drive.healthcheck() is False
