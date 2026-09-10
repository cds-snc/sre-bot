from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from infrastructure.drive.models import DriveFile
from infrastructure.operations import OperationResult


def _http_error(status: int) -> HttpError:
    """Create an HttpError with the given status code for testing."""

    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


@patch("packages.incident.drive.adapters.google_drive.get_drive_provider")
def test_list_child_folders_filters_templates_from_results(mock_get_provider):
    from packages.incident.drive.adapters import google_drive

    provider = MagicMock()
    provider.list_folders.return_value = OperationResult.success(
        data=[
            DriveFile(id="folder-1", name="Alpha"),
            DriveFile(id="folder-2", name="Release Templates"),
            DriveFile(id="folder-3", name="Beta"),
        ]
    )
    mock_get_provider.return_value = provider

    result = google_drive.list_child_folders("parent-folder")

    assert result == [{"id": "folder-1", "name": "Alpha"}, {"id": "folder-3", "name": "Beta"}]
    provider.list_folders.assert_called_once_with("parent-folder")


@patch("packages.incident.drive.adapters.google_drive.get_drive_provider")
def test_find_document_by_channel_name_enriches_match_with_app_properties(mock_get_provider):
    from packages.incident.drive.adapters import google_drive

    provider = MagicMock()
    provider.find_files_by_name.return_value = OperationResult.success(data=[DriveFile(id="doc-1", name="incident-2024-001")])
    mock_get_provider.return_value = provider

    with patch.object(google_drive, "_drive_service") as mock_drive_service:
        files_resource = MagicMock()
        files_resource.get.return_value.execute.return_value = {
            "id": "doc-1",
            "name": "incident-2024-001",
            "appProperties": {"ic_id": "ic-1", "ol_id": "ol-1"},
        }
        mock_service = MagicMock()
        mock_service.files.return_value = files_resource
        mock_drive_service.return_value = mock_service

        result = google_drive.find_document_by_channel_name("2024-001")

    assert result == {"id": "doc-1", "appProperties": {"ic_id": "ic-1", "ol_id": "ol-1"}}
    provider.find_files_by_name.assert_called_once_with("2024-001")
    files_resource.get.assert_called_once_with(fileId="doc-1", fields="id, name, appProperties", supportsAllDrives=True)


@patch("packages.incident.drive.adapters.google_drive.get_drive_provider")
def test_incident_drive_healthcheck_returns_false_when_metadata_lookup_raises(mock_get_provider):
    from packages.incident.drive.adapters import google_drive

    provider = MagicMock()
    mock_get_provider.return_value = provider

    with patch.object(google_drive, "get_metadata", side_effect=RuntimeError("drive down")):
        assert google_drive.incident_drive_healthcheck() is False


def test_add_metadata_returns_updated_file_on_success():
    """add_metadata calls files().update() with appProperties and returns the updated file."""
    from packages.incident.drive.adapters import google_drive

    with patch.object(google_drive, "_drive_service") as mock_drive_service:
        files_resource = MagicMock()
        files_resource.update.return_value.execute.return_value = {
            "id": "file-1",
            "name": "doc",
            "appProperties": {"key": "value"},
        }
        mock_service = MagicMock()
        mock_service.files.return_value = files_resource
        mock_drive_service.return_value = mock_service

        result = google_drive.add_metadata("file-1", "key", "value")

    assert result == {"id": "file-1", "name": "doc", "appProperties": {"key": "value"}}
    files_resource.update.assert_called_once_with(
        fileId="file-1", body={"appProperties": {"key": "value"}}, supportsAllDrives=True
    )


def test_add_metadata_reraises_classified_http_error():
    """add_metadata catches HttpError, classifies it via logger, and re-raises."""
    from packages.incident.drive.adapters import google_drive

    error = _http_error(429)

    with patch.object(google_drive, "_drive_service") as mock_drive_service:
        files_resource = MagicMock()
        files_resource.update.return_value.execute.side_effect = error
        mock_service = MagicMock()
        mock_service.files.return_value = files_resource
        mock_drive_service.return_value = mock_service

        with patch.object(google_drive, "google_workspace_client") as mock_client:
            mock_client.classify_google_error.return_value = (
                SimpleNamespace(value="transient_error"),
                "429",
                7,
            )

            with patch.object(google_drive.logger, "warning") as mock_warning:
                with pytest.raises(HttpError) as exc_info:
                    google_drive.add_metadata("file-1", "key", "value")

                assert exc_info.value is error
                mock_client.classify_google_error.assert_called_once_with(error)
                mock_warning.assert_called_once_with(
                    "incident_drive_add_metadata_failed",
                    file_id="file-1",
                    status="transient_error",
                    error_code="429",
                    retry_after=7,
                )


def test_delete_metadata_returns_updated_file_on_success():
    """delete_metadata calls files().update() with appProperties[key]=None and returns the updated file."""
    from packages.incident.drive.adapters import google_drive

    with patch.object(google_drive, "_drive_service") as mock_drive_service:
        files_resource = MagicMock()
        files_resource.update.return_value.execute.return_value = {
            "id": "file-1",
            "name": "doc",
            "appProperties": {},
        }
        mock_service = MagicMock()
        mock_service.files.return_value = files_resource
        mock_drive_service.return_value = mock_service

        result = google_drive.delete_metadata("file-1", "key")

    assert result == {"id": "file-1", "name": "doc", "appProperties": {}}
    files_resource.update.assert_called_once_with(fileId="file-1", body={"appProperties": {"key": None}}, supportsAllDrives=True)


def test_delete_metadata_reraises_classified_http_error():
    """delete_metadata catches HttpError, classifies it via logger, and re-raises."""
    from packages.incident.drive.adapters import google_drive

    error = _http_error(404)

    with patch.object(google_drive, "_drive_service") as mock_drive_service:
        files_resource = MagicMock()
        files_resource.update.return_value.execute.side_effect = error
        mock_service = MagicMock()
        mock_service.files.return_value = files_resource
        mock_drive_service.return_value = mock_service

        with patch.object(google_drive, "google_workspace_client") as mock_client:
            mock_client.classify_google_error.return_value = (
                SimpleNamespace(value="not_found"),
                "404",
                None,
            )

            with patch.object(google_drive.logger, "warning") as mock_warning:
                with pytest.raises(HttpError) as exc_info:
                    google_drive.delete_metadata("file-1", "key")

                assert exc_info.value is error
                mock_client.classify_google_error.assert_called_once_with(error)
                mock_warning.assert_called_once_with(
                    "incident_drive_delete_metadata_failed",
                    file_id="file-1",
                    status="not_found",
                    error_code="404",
                    retry_after=None,
                )


def test_get_metadata_returns_file_on_success():
    """get_metadata calls files().get() with fields parameter and returns the file."""
    from packages.incident.drive.adapters import google_drive

    with patch.object(google_drive, "_drive_service") as mock_drive_service:
        files_resource = MagicMock()
        files_resource.get.return_value.execute.return_value = {
            "id": "file-1",
            "name": "doc",
            "appProperties": {"key": "value"},
        }
        mock_service = MagicMock()
        mock_service.files.return_value = files_resource
        mock_drive_service.return_value = mock_service

        result = google_drive.get_metadata("file-1", fields="id, name, appProperties")

    assert result == {"id": "file-1", "name": "doc", "appProperties": {"key": "value"}}
    files_resource.get.assert_called_once_with(fileId="file-1", fields="id, name, appProperties", supportsAllDrives=True)


def test_get_metadata_reraises_classified_http_error():
    """get_metadata catches HttpError, classifies it via logger, and re-raises."""
    from packages.incident.drive.adapters import google_drive

    error = _http_error(403)

    with patch.object(google_drive, "_drive_service") as mock_drive_service:
        files_resource = MagicMock()
        files_resource.get.return_value.execute.side_effect = error
        mock_service = MagicMock()
        mock_service.files.return_value = files_resource
        mock_drive_service.return_value = mock_service

        with patch.object(google_drive, "google_workspace_client") as mock_client:
            mock_client.classify_google_error.return_value = (
                SimpleNamespace(value="unauthorized"),
                "403",
                None,
            )

            with patch.object(google_drive.logger, "warning") as mock_warning:
                with pytest.raises(HttpError) as exc_info:
                    google_drive.get_metadata("file-1", fields="id, name, appProperties")

                assert exc_info.value is error
                mock_client.classify_google_error.assert_called_once_with(error)
                mock_warning.assert_called_once_with(
                    "incident_drive_get_metadata_failed",
                    file_id="file-1",
                    status="unauthorized",
                    error_code="403",
                    retry_after=None,
                )
