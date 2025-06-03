"""Unit tests for google_drive module."""

from unittest.mock import patch, call
import pytest
from integrations.google_workspace import google_drive


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_add_metadata_returns_result(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }
    result = google_drive.add_metadata("file_id", "key", "value")
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "update",
        scopes=["test", "scopes"],
        fileId="file_id",
        body={"appProperties": {"key": "value"}},
        fields="name, appProperties",
        supportsAllDrives=True,
    )
    assert result == {"name": "test_folder", "appProperties": {"key": "value"}}


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_delete_metadata_returns_result(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {
        "name": "test_folder",
        "appProperties": {},
    }
    result = google_drive.delete_metadata("file_id", "key")
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "update",
        scopes=["test", "scopes"],
        fileId="file_id",
        body={"appProperties": {"key": None}},
        fields="name, appProperties",
        supportsAllDrives=True,
    )
    assert result == {"name": "test_folder", "appProperties": {}}


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_list_metadata_returns_result(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }
    result = google_drive.list_metadata("file_id")
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "get",
        scopes=["test", "scopes"],
        fileId="file_id",
        fields="id, name, appProperties",
        supportsAllDrives=True,
    )
    assert result == {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_create_folder_returns_folder(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {
        "id": "test_folder_id",
        "name": "test_folder",
        "appProperties": {},
    }
    assert google_drive.create_folder("test_folder", "parent_folder") == {
        "id": "test_folder_id",
        "name": "test_folder",
        "appProperties": {},
    }
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "create",
        scopes=["test", "scopes"],
        body={
            "name": "test_folder",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["parent_folder"],
        },
        supportsAllDrives=True,
        fields=None,
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_create_folder_calls_api_with_fields(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {
        "id": "test_folder_id",
    }
    assert google_drive.create_folder("test_folder", "parent_folder", "id") == {
        "id": "test_folder_id",
    }
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "create",
        scopes=["test", "scopes"],
        body={
            "name": "test_folder",
            "mimeType": "application/vnd.google-apps.folder",
            "parents": ["parent_folder"],
        },
        supportsAllDrives=True,
        fields="id",
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_create_file_with_valid_type_returns_file_id(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {"id": "test_document_id"}
    result = google_drive.create_file("test_document", "folder_id", "document")
    assert result == {"id": "test_document_id"}
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "create",
        scopes=["test", "scopes"],
        body={
            "name": "test_document",
            "mimeType": "application/vnd.google-apps.document",
            "parents": ["folder_id"],
        },
        supportsAllDrives=True,
        fields="id, name",
    )


@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_create_file_with_invalid_type_raises_value_error(execute_google_api_call_mock):
    execute_google_api_call_mock.side_effect = ValueError(
        "Invalid file_type: invalid_file_type"
    )
    with pytest.raises(ValueError):
        result = google_drive.create_file("name", "folder", "invalid_file_type")
        assert result is None


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_create_file_from_template_returns_file(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {"id": "test_document_id"}
    result = google_drive.create_file_from_template(
        "test_document", "folder_id", "template_id"
    )
    assert result == {"id": "test_document_id"}
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "copy",
        scopes=["test", "scopes"],
        fileId="template_id",
        body={"name": "test_document", "parents": ["folder_id"]},
        supportsAllDrives=True,
        fields=None,
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_get_file_by_id(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = {
        "name": "test_document",
        "id": "test_document_id",
        "appProperties": {},
    }
    result = google_drive.get_file_by_id("test_document_id")
    assert result == {
        "name": "test_document",
        "id": "test_document_id",
        "appProperties": {},
    }
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "get",
        scopes=["test", "scopes"],
        fileId="test_document_id",
        supportsAllDrives=True,
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_find_files_by_name_with_folder_id_returns_object(execute_google_api_call_mock):
    execute_google_api_call_mock.return_value = [
        {
            "name": "test_document",
            "id": "test_document_id",
            "appProperties": {},
        }
    ]
    result = google_drive.find_files_by_name("test_file_name", "folder_id")
    assert result == [
        {
            "name": "test_document",
            "id": "test_document_id",
            "appProperties": {},
        }
    ]
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["test", "scopes"],
        paginate=True,
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q="trashed=false and name='test_file_name' and 'folder_id' in parents",
        fields="files(appProperties, id, name)",
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_find_files_by_name_without_folder_id_returns_object(
    execute_google_api_call_mock,
):
    execute_google_api_call_mock.return_value = [
        {
            "name": "test_document",
            "id": "test_document_id",
            "appProperties": {},
        }
    ]
    result = google_drive.find_files_by_name("test_file_name")
    assert result == [
        {
            "name": "test_document",
            "id": "test_document_id",
            "appProperties": {},
        }
    ]
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["test", "scopes"],
        paginate=True,
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q="trashed=false and name='test_file_name'",
        fields="files(appProperties, id, name)",
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_find_files_by_name_with_empty_folder_id_returns_object(
    execute_google_api_call_mock,
):
    execute_google_api_call_mock.return_value = [
        {
            "name": "test_document",
            "id": "test_document_id",
            "appProperties": {},
        }
    ]
    result = google_drive.find_files_by_name("test_file_name", "")
    assert result == [
        {
            "name": "test_document",
            "id": "test_document_id",
            "appProperties": {},
        }
    ]
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["test", "scopes"],
        paginate=True,
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q="trashed=false and name='test_file_name'",
        fields="files(appProperties, id, name)",
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_find_files_by_name_no_file_found_returns_empty_list(
    execute_google_api_call_mock,
):
    execute_google_api_call_mock.return_value = []
    result = google_drive.find_files_by_name("test_file_name", "folder_id")
    assert result == []
    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["test", "scopes"],
        paginate=True,
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q="trashed=false and name='test_file_name' and 'folder_id' in parents",
        fields="files(appProperties, id, name)",
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_copy_file_to_folder_returns_file_id(execute_google_api_call_mock):
    execute_google_api_call_mock.side_effect = [
        [{"id": "file_id"}],  # Response from the "copy" method
        [{"id": "updated_file_id"}],  # Response from the "update" method
    ]
    assert (
        google_drive.copy_file_to_folder(
            "file_id", "name", "parent_folder", "destination_folder"
        )
        == "updated_file_id"
    )
    execute_google_api_call_mock.assert_has_calls(
        [
            call(
                "drive",
                "v3",
                "files",
                "copy",
                scopes=["test", "scopes"],
                fileId="file_id",
                body={"name": "name", "parents": ["parent_folder"]},
                supportsAllDrives=True,
                fields="id",
            ),
            call(
                "drive",
                "v3",
                "files",
                "update",
                scopes=["test", "scopes"],
                fileId="file_id",
                addParents="destination_folder",
                removeParents="parent_folder",
                supportsAllDrives=True,
                fields="id",
            ),
        ]
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_list_folders_in_folder_returns_folders(execute_google_api_call_mock):
    # Mock the results
    results = [
        {"id": "test_folder_id", "name": "test_folder"},
        {"id": "test_folder_id2", "name": "test_folder2"},
    ]

    # Mock execute_google_api_call to return the results
    execute_google_api_call_mock.return_value = results

    assert google_drive.list_folders_in_folder("parent_folder") == results

    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["test", "scopes"],
        paginate=True,
        pageSize=25,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q="parents in 'parent_folder' and mimeType = 'application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_list_folders_in_folder_with_query(execute_google_api_call_mock):
    # Mock the results
    results = [
        {"id": "test_folder_id", "name": "test_folder"},
        {"id": "test_folder_id2", "name": "test_folder2"},
    ]
    query = "some_query"

    # Mock execute_google_api_call to return the results
    execute_google_api_call_mock.return_value = results

    assert google_drive.list_folders_in_folder("parent_folder", query) == results

    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["test", "scopes"],
        paginate=True,
        pageSize=25,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q="parents in 'parent_folder' and mimeType = 'application/vnd.google-apps.folder' and trashed=false and some_query",
        fields="files(id, name)",
    )


@patch("integrations.google_workspace.google_drive.SCOPES", ["test", "scopes"])
@patch(
    "integrations.google_workspace.google_drive.google_service.execute_google_api_call"
)
def test_list_files_in_folder_returns_files(execute_google_api_call_mock):
    # Mock the results
    results = [
        {"id": "test_file_id", "name": "test_file"},
        {"id": "test_file_id2", "name": "test_file2"},
    ]

    # Mock execute_google_api_call to return the results
    execute_google_api_call_mock.return_value = results

    assert google_drive.list_files_in_folder("parent_folder") == results

    execute_google_api_call_mock.assert_called_once_with(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["test", "scopes"],
        paginate=True,
        pageSize=25,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q="parents in 'parent_folder' and mimeType != 'application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    )


@patch("integrations.google_workspace.google_drive.list_metadata")
def test_healthcheck_healthy(list_metadata_mock):
    list_metadata_mock.return_value = {"id": "test_doc"}
    assert google_drive.healthcheck() is True


@patch("integrations.google_workspace.google_drive.list_metadata")
def test_healthcheck_unhealthy(list_metadata_mock):
    list_metadata_mock.return_value = None
    assert google_drive.healthcheck() is False
