"""Behavior contract for the Google-backed DriveProvider implementation."""

from unittest.mock import MagicMock

import httplib2
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
    return GoogleDriveProvider(
        get_service=lambda scopes, delegated_user_email=None: drive_service,
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
    assert files_resource.list.call_count == 2


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
        app_properties={"key": "value"},
        provider="google",
    )

    assert item.id == "file-1"
    assert item.parents == ("root",)
    assert item.mime_type == "application/vnd.google-apps.folder"
    with pytest.raises(FrozenInstanceError):
        item.name = "changed"
