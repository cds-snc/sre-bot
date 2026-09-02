"""Unit tests for the google_drive module."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call

import pytest
from googleapiclient.errors import HttpError

from integrations.google_workspace import client as google_client
from integrations.google_workspace import google_drive

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


def _page_request(response: dict) -> MagicMock:
    """A built list request whose execute() yields one page."""
    request = MagicMock()
    request.execute.return_value = response
    return request


@pytest.fixture
def drive_client(monkeypatch):
    """Patch the Drive service factory and expose the mocked stub-typed Resource chain."""
    if not hasattr(google_client, "get_drive_service"):
        pytest.fail("integrations.google_workspace.client.get_drive_service is not implemented")

    service = MagicMock()
    factory = MagicMock(return_value=service)
    monkeypatch.setattr(google_client, "get_drive_service", factory)
    if hasattr(google_drive, "get_drive_service"):
        monkeypatch.setattr(google_drive, "get_drive_service", factory)
    return SimpleNamespace(factory=factory, service=service, files=service.files.return_value)


# AC#1/#7: the dispatcher is gone from this module.
def test_module_does_not_reference_the_legacy_dispatcher():
    assert not hasattr(google_drive, "google_service")
    assert "execute_google_api_call" not in Path(google_drive.__file__).read_text()


def test_module_hardcodes_no_field_projection():
    """appProperties is a caller convention, not an SDK default, so the projection belongs to consumers."""
    assert "appProperties" not in Path(google_drive.__file__).read_text()


# --- add_metadata ------------------------------------------------------- AC#1, AC#2


def test_add_metadata_calls_files_update_and_returns_result(drive_client):
    update_call = drive_client.files.update
    update_call.return_value.execute.return_value = {
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }

    result = google_drive.add_metadata("file_id", "key", "value")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    update_call.assert_called_once_with(
        fileId="file_id",
        body={"appProperties": {"key": "value"}},
        fields=None,
        supportsAllDrives=True,
    )
    assert result == {"name": "test_folder", "appProperties": {"key": "value"}}


def test_add_metadata_forwards_a_caller_supplied_projection(drive_client):
    drive_client.files.update.return_value.execute.return_value = {}

    google_drive.add_metadata("file_id", "key", "value", fields="name, appProperties")

    assert drive_client.files.update.call_args.kwargs["fields"] == "name, appProperties"


def test_add_metadata_passes_delegated_user_email(drive_client):
    drive_client.files.update.return_value.execute.return_value = {}

    google_drive.add_metadata("file_id", "key", "value", delegated_user_email="custom@example.com")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email="custom@example.com")


def test_add_metadata_propagates_http_error(drive_client):
    error = _http_error(429)
    drive_client.files.update.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.add_metadata("file_id", "key", "value")

    assert exc_info.value is error


# --- delete_metadata ---------------------------------------------------- AC#1, AC#2


def test_delete_metadata_calls_files_update_and_returns_result(drive_client):
    update_call = drive_client.files.update
    update_call.return_value.execute.return_value = {"name": "test_folder", "appProperties": {}}

    result = google_drive.delete_metadata("file_id", "key")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    update_call.assert_called_once_with(
        fileId="file_id",
        body={"appProperties": {"key": None}},
        fields=None,
        supportsAllDrives=True,
    )
    assert result == {"name": "test_folder", "appProperties": {}}


def test_delete_metadata_propagates_http_error(drive_client):
    error = _http_error(404)
    drive_client.files.update.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.delete_metadata("file_id", "key")

    assert exc_info.value is error


# --- list_metadata ------------------------------------------------------ AC#1, AC#2, AC#5


def test_list_metadata_calls_files_get_without_a_default_projection(drive_client):
    get_call = drive_client.files.get
    get_call.return_value.execute.return_value = {"name": "test_folder"}

    result = google_drive.list_metadata("file_id")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    get_call.assert_called_once_with(
        fileId="file_id",
        fields=None,
        supportsAllDrives=True,
    )
    assert result == {"name": "test_folder"}


def test_list_metadata_forwards_a_caller_supplied_projection(drive_client):
    get_call = drive_client.files.get
    get_call.return_value.execute.return_value = {
        "id": "file_id",
        "name": "test_folder",
        "appProperties": {"key": "value"},
    }

    result = google_drive.list_metadata("file_id", fields="id, name, appProperties")

    assert get_call.call_args.kwargs["fields"] == "id, name, appProperties"
    assert result["appProperties"] == {"key": "value"}


def test_list_metadata_propagates_http_error(drive_client):
    error = _http_error(403)
    drive_client.files.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.list_metadata("file_id")

    assert exc_info.value is error


# --- get_file_by_id ----------------------------------------------------- AC#1, AC#5


def test_get_file_by_id_calls_files_get(drive_client):
    get_call = drive_client.files.get
    get_call.return_value.execute.return_value = {
        "name": "test_document",
        "id": "test_document_id",
        "appProperties": {},
    }

    result = google_drive.get_file_by_id("test_document_id")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    get_call.assert_called_once_with(
        fileId="test_document_id",
        fields=None,
        supportsAllDrives=True,
    )
    assert result == {"name": "test_document", "id": "test_document_id", "appProperties": {}}


def test_get_file_by_id_propagates_http_error(drive_client):
    error = _http_error(404)
    drive_client.files.get.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.get_file_by_id("test_document_id")

    assert exc_info.value is error


# --- create_folder ------------------------------------------------------ AC#1, AC#2, AC#5


def test_create_folder_calls_files_create_and_returns_folder(drive_client):
    create_call = drive_client.files.create
    create_call.return_value.execute.return_value = {
        "id": "test_folder_id",
        "name": "test_folder",
        "appProperties": {},
    }

    result = google_drive.create_folder("test_folder", "parent_folder")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    create_call.assert_called_once_with(
        body={
            "name": "test_folder",
            "parents": ["parent_folder"],
            "mimeType": "application/vnd.google-apps.folder",
        },
        supportsAllDrives=True,
        fields=None,
    )
    assert result == {"id": "test_folder_id", "name": "test_folder", "appProperties": {}}


def test_create_folder_keeps_fields_as_third_positional_argument(drive_client):
    """modules/role/role.py passes fields positionally; that call shape must keep working."""
    create_call = drive_client.files.create
    create_call.return_value.execute.return_value = {"id": "test_folder_id"}

    result = google_drive.create_folder(
        "test_folder",
        "parent_folder",
        "id",
        delegated_user_email="bot@example.com",
    )

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email="bot@example.com")
    assert create_call.call_args.kwargs["fields"] == "id"
    assert result == {"id": "test_folder_id"}


def test_create_folder_propagates_http_error(drive_client):
    error = _http_error(500)
    drive_client.files.create.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.create_folder("test_folder", "parent_folder")

    assert exc_info.value is error


# --- create_file -------------------------------------------------------- AC#1, AC#2, AC#5


def test_create_file_with_valid_type_calls_files_create(drive_client):
    create_call = drive_client.files.create
    create_call.return_value.execute.return_value = {"id": "test_document_id"}

    result = google_drive.create_file("test_document", "folder_id", "document")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    create_call.assert_called_once_with(
        body={
            "name": "test_document",
            "parents": ["folder_id"],
            "mimeType": "application/vnd.google-apps.document",
        },
        supportsAllDrives=True,
        fields="id, name",
    )
    assert result == {"id": "test_document_id"}


def test_create_file_with_invalid_type_raises_before_building_a_service(drive_client):
    with pytest.raises(ValueError, match="Invalid file_type: invalid_file_type"):
        google_drive.create_file("name", "folder", "invalid_file_type")

    drive_client.factory.assert_not_called()


def test_create_file_propagates_http_error(drive_client):
    error = _http_error(503)
    drive_client.files.create.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.create_file("test_document", "folder_id", "document")

    assert exc_info.value is error


# --- create_file_from_template ------------------------------------------ AC#1, AC#2, AC#5


def test_create_file_from_template_calls_files_copy(drive_client):
    copy_call = drive_client.files.copy
    copy_call.return_value.execute.return_value = {"id": "test_document_id"}

    result = google_drive.create_file_from_template("test_document", "folder_id", "template_id")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    copy_call.assert_called_once_with(
        fileId="template_id",
        body={"name": "test_document", "parents": ["folder_id"]},
        supportsAllDrives=True,
        fields=None,
    )
    assert result == {"id": "test_document_id"}


def test_create_file_from_template_propagates_http_error(drive_client):
    error = _http_error(404)
    drive_client.files.copy.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.create_file_from_template("test_document", "folder_id", "template_id")

    assert exc_info.value is error


# --- copy_file_to_folder ------------------------------------------------ AC#1, AC#2, AC#5


def test_copy_file_to_folder_copies_then_moves_and_returns_updated_id(drive_client):
    drive_client.files.copy.return_value.execute.return_value = {"id": "copied_file_id"}
    drive_client.files.update.return_value.execute.return_value = {"id": "updated_file_id"}

    result = google_drive.copy_file_to_folder("file_id", "name", "parent_folder", "destination_folder")

    assert result == "updated_file_id"
    drive_client.files.copy.assert_called_once_with(
        fileId="file_id",
        body={"name": "name", "parents": ["parent_folder"]},
        supportsAllDrives=True,
        fields="id",
    )
    drive_client.files.update.assert_called_once_with(
        fileId="copied_file_id",
        body={},
        addParents="destination_folder",
        removeParents="parent_folder",
        supportsAllDrives=True,
        fields="id",
    )
    method_order = [c[0] for c in drive_client.files.mock_calls if c[0] in {"copy", "update"}]
    assert method_order == ["copy", "update"]


def test_copy_file_to_folder_builds_one_service_for_both_calls(drive_client):
    drive_client.files.copy.return_value.execute.return_value = {"id": "copied_file_id"}
    drive_client.files.update.return_value.execute.return_value = {"id": "updated_file_id"}

    google_drive.copy_file_to_folder("file_id", "name", "parent_folder", "destination_folder")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)


def test_copy_file_to_folder_propagates_http_error(drive_client):
    error = _http_error(403)
    drive_client.files.copy.return_value.execute.side_effect = error

    with pytest.raises(HttpError) as exc_info:
        google_drive.copy_file_to_folder("file_id", "name", "parent_folder", "destination_folder")

    assert exc_info.value is error


# --- find_files_by_name --------------------------------------- AC#1, AC#2, AC#3, AC#5


def test_find_files_by_name_with_folder_id_builds_scoped_query(drive_client):
    files_page = [{"name": "test_document", "id": "test_document_id"}]
    drive_client.files.list.return_value = _page_request({"files": files_page})
    drive_client.files.list_next.return_value = None

    result = google_drive.find_files_by_name("test_file_name", "folder_id")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    drive_client.files.list.assert_called_once_with(
        q="trashed=false and name='test_file_name' and 'folder_id' in parents",
        fields=None,
        pageSize=100,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
    )
    assert result == files_page


def test_find_files_by_name_forwards_a_caller_supplied_projection(drive_client):
    """Callers that need appProperties own the projection, including its nextPageToken."""
    drive_client.files.list.return_value = _page_request({"files": [{"appProperties": {"ic_id": "ic"}}]})
    drive_client.files.list_next.return_value = None

    result = google_drive.find_files_by_name(
        "test_file_name",
        fields="nextPageToken, files(appProperties, id, name)",
    )

    assert drive_client.files.list.call_args.kwargs["fields"] == "nextPageToken, files(appProperties, id, name)"
    assert result == [{"appProperties": {"ic_id": "ic"}}]


def test_find_files_by_name_without_folder_id_builds_unscoped_query(drive_client):
    drive_client.files.list.return_value = _page_request({"files": []})
    drive_client.files.list_next.return_value = None

    assert google_drive.find_files_by_name("test_file_name") == []

    assert drive_client.files.list.call_args.kwargs["q"] == "trashed=false and name='test_file_name'"


def test_find_files_by_name_with_empty_folder_id_builds_unscoped_query(drive_client):
    drive_client.files.list.return_value = _page_request({"files": []})
    drive_client.files.list_next.return_value = None

    assert google_drive.find_files_by_name("test_file_name", "") == []

    assert drive_client.files.list.call_args.kwargs["q"] == "trashed=false and name='test_file_name'"


def test_find_files_by_name_follows_every_page(drive_client):
    """AC#3: no fields= projection is set by default, so nextPageToken comes back and list_next advances."""
    first_page = {"files": [{"id": "1"}], "nextPageToken": "token"}
    second_page = {"files": [{"id": "2"}]}
    first_request = _page_request(first_page)
    second_request = _page_request(second_page)
    drive_client.files.list.return_value = first_request
    drive_client.files.list_next.side_effect = [second_request, None]

    result = google_drive.find_files_by_name("test_file_name")

    assert result == [{"id": "1"}, {"id": "2"}]
    drive_client.files.list_next.assert_has_calls([call(first_request, first_page), call(second_request, second_page)])


def test_find_files_by_name_propagates_http_error(drive_client):
    error = _http_error(429)
    request = MagicMock()
    request.execute.side_effect = error
    drive_client.files.list.return_value = request

    with pytest.raises(HttpError) as exc_info:
        google_drive.find_files_by_name("test_file_name")

    assert exc_info.value is error


# --- list_folders_in_folder ----------------------------------- AC#1, AC#2, AC#3, AC#5


def test_list_folders_in_folder_returns_folders(drive_client):
    folders = [
        {"id": "test_folder_id", "name": "test_folder"},
        {"id": "test_folder_id2", "name": "test_folder2"},
    ]
    drive_client.files.list.return_value = _page_request({"files": folders})
    drive_client.files.list_next.return_value = None

    result = google_drive.list_folders_in_folder("parent_folder")

    drive_client.factory.assert_called_once_with(scopes=DRIVE_SCOPES, delegated_user_email=None)
    drive_client.files.list.assert_called_once_with(
        q="parents in 'parent_folder' and mimeType = 'application/vnd.google-apps.folder' and trashed=false",
        fields=None,
        pageSize=100,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
    )
    assert result == folders


def test_list_folders_in_folder_appends_extra_query(drive_client):
    drive_client.files.list.return_value = _page_request({"files": []})
    drive_client.files.list_next.return_value = None

    google_drive.list_folders_in_folder("parent_folder", "some_query")

    assert drive_client.files.list.call_args.kwargs["q"] == (
        "parents in 'parent_folder' and mimeType = 'application/vnd.google-apps.folder' and trashed=false and some_query"
    )


def test_list_folders_in_folder_is_not_truncated(drive_client):
    """AC#3: the previously-latent pageSize=25 truncation is gone."""
    page_one = {"files": [{"id": str(i)} for i in range(100)], "nextPageToken": "token"}
    page_two = {"files": [{"id": "100"}]}
    drive_client.files.list.return_value = _page_request(page_one)
    drive_client.files.list_next.side_effect = [_page_request(page_two), None]

    assert len(google_drive.list_folders_in_folder("parent_folder")) == 101


def test_list_folders_in_folder_propagates_http_error(drive_client):
    error = _http_error(500)
    request = MagicMock()
    request.execute.side_effect = error
    drive_client.files.list.return_value = request

    with pytest.raises(HttpError) as exc_info:
        google_drive.list_folders_in_folder("parent_folder")

    assert exc_info.value is error


# --- list_files_in_folder ------------------------------------- AC#1, AC#2, AC#3, AC#5


def test_list_files_in_folder_returns_files(drive_client):
    files = [
        {"id": "test_file_id", "name": "test_file"},
        {"id": "test_file_id2", "name": "test_file2"},
    ]
    drive_client.files.list.return_value = _page_request({"files": files})
    drive_client.files.list_next.return_value = None

    result = google_drive.list_files_in_folder("parent_folder")

    drive_client.files.list.assert_called_once_with(
        q="parents in 'parent_folder' and mimeType != 'application/vnd.google-apps.folder' and trashed=false",
        fields=None,
        pageSize=100,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
    )
    assert result == files


def test_list_files_in_folder_skips_pages_without_files_key(drive_client):
    drive_client.files.list.return_value = _page_request({"nextPageToken": "token"})
    drive_client.files.list_next.side_effect = [_page_request({"files": [{"id": "1"}]}), None]

    assert google_drive.list_files_in_folder("parent_folder") == [{"id": "1"}]


def test_list_files_in_folder_propagates_http_error(drive_client):
    error = _http_error(401)
    request = MagicMock()
    request.execute.side_effect = error
    drive_client.files.list.return_value = request

    with pytest.raises(HttpError) as exc_info:
        google_drive.list_files_in_folder("parent_folder")

    assert exc_info.value is error


# --- healthcheck --------------------------------------------------------- AC#5


def test_healthcheck_healthy(monkeypatch):
    monkeypatch.setattr(google_drive, "list_metadata", lambda *args, **kwargs: {"id": "test_doc"})
    assert google_drive.healthcheck() is True


def test_healthcheck_unhealthy(monkeypatch):
    monkeypatch.setattr(google_drive, "list_metadata", lambda *args, **kwargs: None)
    assert google_drive.healthcheck() is False


def test_healthcheck_swallows_errors(monkeypatch):
    def raise_error(*args, **kwargs):
        raise _http_error(500)

    monkeypatch.setattr(google_drive, "list_metadata", raise_error)
    assert google_drive.healthcheck() is False
