"""Behavior-focused tests for Drive boundary handling in incident_draft adapter."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from infrastructure.operations.status import OperationStatus
from packages.incident_draft.adapters import google_docs as adapter

pytestmark = pytest.mark.unit

_DRIVE = "packages.incident_draft.adapters.google_docs.google_drive"
_CLIENT = "packages.incident_draft.adapters.google_docs.google_workspace_client"
_CONFIG = "packages.incident_draft.adapters.google_docs.get_google_resources_config"


def _http_error(status: int) -> HttpError:
    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


def _drive_resource(*, copy_response: dict | None = None, get_response: dict | None = None) -> MagicMock:
    service = MagicMock()
    if copy_response is not None:
        service.files.return_value.copy.return_value.execute.return_value = copy_response
    if get_response is not None:
        service.files.return_value.get.return_value.execute.return_value = get_response
    return service


def test_copy_source_document_uses_drive_service_copy_boundary():
    with patch(_DRIVE) as mock_drive, patch(_CLIENT, create=True) as mock_client:
        mock_drive.create_file_from_template.return_value = {"id": "legacy-id"}
        mock_client.get_drive_service.return_value = _drive_resource(copy_response={"id": "new-id"})

        copied_id = adapter._copy_source_document("SRC-1", "Draft title", "FOLDER-1")

    assert copied_id == "new-id"
    mock_client.get_drive_service.assert_called_once_with(scopes=mock_drive.DRIVE_SCOPES)
    mock_client.get_drive_service.return_value.files.return_value.copy.assert_called_once_with(
        fileId="SRC-1",
        body={"name": "Draft title", "parents": ["FOLDER-1"]},
        supportsAllDrives=True,
        fields="id",
    )
    mock_drive.create_file_from_template.assert_not_called()


def test_source_name_and_folder_uses_drive_service_get_boundary():
    with patch(_DRIVE) as mock_drive, patch(_CLIENT, create=True) as mock_client:
        mock_drive.get_file_by_id.return_value = {"name": "legacy", "parents": ["legacy-folder"]}
        mock_client.get_drive_service.return_value = _drive_resource(
            get_response={"name": "Source report", "parents": ["PARENT-1"]}
        )

        source_name, source_folder = adapter._source_name_and_folder("DOC-1")

    assert source_name == "Source report"
    assert source_folder == "PARENT-1"
    mock_client.get_drive_service.assert_called_once_with(scopes=mock_drive.DRIVE_SCOPES)
    mock_client.get_drive_service.return_value.files.return_value.get.assert_called_once_with(
        fileId="DOC-1",
        fields="id, name, parents",
        supportsAllDrives=True,
    )
    mock_drive.get_file_by_id.assert_not_called()


def test_copy_source_document_http_error_returns_none_after_classification():
    error = _http_error(503)
    with patch(_DRIVE) as mock_drive, patch(_CLIENT, create=True) as mock_client:
        mock_drive.create_file_from_template.side_effect = error
        service = _drive_resource()
        service.files.return_value.copy.return_value.execute.side_effect = error
        mock_client.get_drive_service.return_value = service
        mock_client.classify_google_error.return_value = (OperationStatus.TRANSIENT_ERROR, "503", 10)

        copied_id = adapter._copy_source_document("SRC-2", "Draft title", "FOLDER-2")

    assert copied_id is None
    mock_client.classify_google_error.assert_called_once_with(error)


def test_source_name_and_folder_http_error_falls_back_to_configured_folder():
    error = _http_error(404)
    with patch(_DRIVE) as mock_drive, patch(_CLIENT, create=True) as mock_client, patch(_CONFIG) as mock_config:
        mock_drive.get_file_by_id.side_effect = error
        service = _drive_resource()
        service.files.return_value.get.return_value.execute.side_effect = error
        mock_client.get_drive_service.return_value = service
        mock_client.classify_google_error.return_value = (OperationStatus.NOT_FOUND, "404", None)
        mock_config.return_value = SimpleNamespace(incident_folder_id="fallback-folder")

        source_name, source_folder = adapter._source_name_and_folder("DOC-2")

    assert source_name == "Incident report"
    assert source_folder == "fallback-folder"
    mock_client.classify_google_error.assert_called_once_with(error)
