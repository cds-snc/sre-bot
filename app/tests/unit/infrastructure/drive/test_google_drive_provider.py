"""Behavior contract for the Google-backed DriveProvider implementation."""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest
from googleapiclient.errors import HttpError

from infrastructure.drive.google import GoogleDriveProvider
from infrastructure.drive.models import DriveFile
from infrastructure.drive.provider import DriveProvider
from infrastructure.operations.status import OperationStatus


class FakeResp(dict):
    def __init__(self, status: int) -> None:
        super().__init__()
        self.status = status
        self.reason = "boom"


def _http_error(status: int) -> HttpError:
    return HttpError(resp=FakeResp(status), content=b"{}")


def _request(payload):
    request = MagicMock()
    request.execute.return_value = payload
    return request


@pytest.fixture
def drive_service():
    service = MagicMock()
    files = service.files.return_value
    files.list.return_value = _request({"files": []})
    files.list_next.return_value = None
    files.create.return_value = _request({"id": "file-123", "name": "New folder"})
    files.copy.return_value = _request({"id": "copy-123", "name": "Copied file"})
    files.update.return_value = _request({"id": "copy-123", "name": "Moved file"})
    files.get.return_value = _request({"id": "file-123", "name": "Target file"})
    return service


@pytest.fixture
def provider(drive_service):
    get_service = MagicMock(return_value=drive_service)
    return GoogleDriveProvider(
        get_service=get_service,
        drive_settings=MagicMock(),
    )


def test_provider_satisfies_drive_protocol(provider):
    assert isinstance(provider, DriveProvider)


def test_list_folders_paginates_across_multiple_pages(provider, drive_service):
    files_resource = drive_service.files.return_value
    first = _request({"files": [{"id": "f-1", "name": "Folder 1", "mimeType": "application/vnd.google-apps.folder"}]})
    second = _request({"files": [{"id": "f-2", "name": "Folder 2", "mimeType": "application/vnd.google-apps.folder"}]})
    files_resource.list.side_effect = [first, second]
    files_resource.list_next.side_effect = [second, None]

    result = provider.list_folders("parent-1")

    assert result.is_success
    assert [item.id for item in result.data] == ["f-1", "f-2"]
    files_resource.list.assert_called_once()
    assert files_resource.list_next.call_count == 2


def test_list_folders_preserves_query_composition_and_delegation(provider, drive_service):
    result = provider.list_folders(
        "parent-1", "name contains 'Reports'", fields="files(id)", delegated_user_email="user@example.com"
    )

    assert result.is_success
    assert drive_service.files.return_value.list.call_args.kwargs["q"] == (
        "parents in 'parent-1' and mimeType = 'application/vnd.google-apps.folder' and trashed=false and name contains 'Reports'"
    )
    assert provider._get_service.call_args.args == (  # type: ignore[attr-defined]
        ["https://www.googleapis.com/auth/drive"],
        "user@example.com",
    )


def test_find_files_by_name_preserves_query_composition(provider, drive_service):
    result = provider.find_files_by_name("Report", "parent-1")

    assert result.is_success
    assert (
        drive_service.files.return_value.list.call_args.kwargs["q"] == "trashed=false and name='Report' and 'parent-1' in parents"
    )


def test_create_folder_and_template_copy_map_drive_files(provider, drive_service):
    files_resource = drive_service.files.return_value
    files_resource.create.return_value = _request(
        {"id": "folder-1", "name": "Reports", "mimeType": "application/vnd.google-apps.folder"}
    )
    files_resource.copy.return_value = _request({"id": "file-1", "name": "Report"})

    folder_result = provider.create_folder("Reports", "parent-1", fields="id", delegated_user_email="user@example.com")
    template_result = provider.create_file_from_template("Report", "parent-1", "template-1")

    assert folder_result.is_success
    assert folder_result.data == DriveFile(
        id="folder-1", name="Reports", mime_type="application/vnd.google-apps.folder", provider="google"
    )
    assert template_result.is_success
    assert template_result.data == DriveFile(id="file-1", name="Report", provider="google")
    assert files_resource.create.call_args.kwargs["body"] == {
        "name": "Reports",
        "parents": ["parent-1"],
        "mimeType": "application/vnd.google-apps.folder",
    }
    assert files_resource.copy.call_args.kwargs["body"] == {"name": "Report", "parents": ["parent-1"]}


def test_warmup_calls_cheap_drive_probe_and_health_check_is_local(provider, drive_service):
    assert provider.warmup().is_success
    drive_service.files.assert_called()
    assert provider.health_check().is_success


@pytest.mark.parametrize(
    "operation",
    [
        lambda provider: provider.create_folder("Reports", "parent-1"),
        lambda provider: provider.create_file_from_template("Report", "parent-1", "template-1"),
        lambda provider: provider.find_files_by_name("Report"),
    ],
)
def test_http_errors_are_classified_for_each_drive_operation(provider, drive_service, operation):
    files_resource = drive_service.files.return_value
    files_resource.create.side_effect = _http_error(429)
    files_resource.copy.side_effect = _http_error(429)
    files_resource.list.side_effect = _http_error(429)
    files_resource.get.side_effect = _http_error(429)
    files_resource.update.side_effect = _http_error(429)

    result = operation(provider)

    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "429"


def test_copy_file_to_folder_uses_copy_then_move_sequence(provider, drive_service):
    files_resource = drive_service.files.return_value
    files_resource.copy.return_value = _request({"id": "copied-1", "name": "Template copy"})
    files_resource.update.return_value = _request({"id": "copied-1", "name": "Template copy"})

    result = provider.copy_file_to_folder(
        "source-file-id",
        "Template copy",
        "source-parent",
        "destination-folder",
    )

    assert result.is_success
    assert result.data.id == "copied-1"
    assert files_resource.copy.call_count == 1
    assert files_resource.update.call_count == 1
    assert files_resource.update.call_args.kwargs["addParents"] == "destination-folder"
    assert files_resource.update.call_args.kwargs["removeParents"] == "source-parent"


def test_http_errors_are_classified_into_operation_result(provider, drive_service):
    files_resource = drive_service.files.return_value
    files_resource.list.side_effect = _http_error(429)

    result = provider.list_files("parent-1")

    assert not result.is_success
    assert result.status == OperationStatus.TRANSIENT_ERROR
    assert result.error_code == "429"


def test_drive_file_is_frozen_and_canonical_for_folders_and_files():
    item = DriveFile(
        id="file-1",
        name="Folder 1",
        mime_type="application/vnd.google-apps.folder",
        parents=("root",),
        provider="google",
    )

    assert item.id == "file-1"
    assert item.parents == ("root",)
    assert item.mime_type == "application/vnd.google-apps.folder"
    with pytest.raises(FrozenInstanceError):
        item.name = "changed"
