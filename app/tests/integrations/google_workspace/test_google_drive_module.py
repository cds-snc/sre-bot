"""Unit tests for google_drive module."""
import pytest
from unittest.mock import patch

import integrations.google_workspace.google_drive as google_drive

# Constants for the test
START_HEADING = "Detailed Timeline"
END_HEADING = "Trigger"


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
def test_create_folder_returns_folder_id(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "test_folder_id"
    }
    result = google_drive.create_folder("test_folder", "parent_folder")
    assert result == "test_folder_id"


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_create_new_file_with_valid_type_returns_file_id(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.create.return_value.execute.return_value = {
        "id": "test_document_id"
    }
    result = google_drive.create_new_file("test_document", "folder_id", "document")
    assert result == "test_document_id"


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_create_new_file_with_invalid_type_raises_value_error(get_google_service_mock):
    with pytest.raises(ValueError) as e:
        google_drive.create_new_file("test_document", "folder_id", "invalid_type")
    assert "Invalid file_type: invalid_type" in str(e.value)


@patch("integrations.google_workspace.google_drive.get_google_service")
def test_create_new_file_from_template_returns_file_id(get_google_service_mock):
    get_google_service_mock.return_value.files.return_value.copy.return_value.execute.return_value = {
        "id": "test_document_id"
    }
    result = google_drive.create_new_file_from_template(
        "test_document", "folder_id", "template_id"
    )
    assert result == "test_document_id"


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
