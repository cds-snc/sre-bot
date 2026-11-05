from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError
from structlog.testing import capture_logs

from contracts.operations.status import OperationStatus
from features.incident.core.adapters import google_docs as google_drive


def _http_error(status: int) -> HttpError:
    """Create an HttpError with the given status code for testing."""

    class FakeResp(dict):
        def __init__(self) -> None:
            super().__init__()
            self.status = status
            self.reason = "boom"

    return HttpError(resp=FakeResp(), content=b"{}")


FOLDER_MIME = "application/vnd.google-apps.folder"


def _drive_with_pages(*pages: list[dict]) -> MagicMock:
    """A Drive service whose files().list returns ``pages`` in turn through list_next."""
    service = MagicMock()
    files = service.files.return_value
    requests = [MagicMock(name=f"page-{index}") for index in range(len(pages))]
    for request, page in zip(requests, pages, strict=True):
        request.execute.return_value = {"files": page}
    files.list.return_value = requests[0]
    files.list_next.side_effect = [*requests[1:], None]
    return service


def _list_kwargs(query: str) -> dict:
    return {
        "q": query,
        "pageSize": 100,
        "supportsAllDrives": True,
        "includeItemsFromAllDrives": True,
        "corpora": "user",
    }


def test_list_child_folders_reads_every_page_and_filters_templates():
    """Folders are listed across pages, shared drives included, and template folders are left out."""
    service = _drive_with_pages(
        [{"id": "folder-1", "name": "Alpha"}, {"id": "folder-2", "name": "Release Templates"}],
        [{"id": "folder-3", "name": "Beta"}],
    )
    with patch.object(google_drive, "_drive_service", return_value=service):
        result = google_drive.list_child_folders("parent-folder")

    assert result == [{"id": "folder-1", "name": "Alpha"}, {"id": "folder-3", "name": "Beta"}]
    service.files.return_value.list.assert_called_once_with(
        **_list_kwargs(f"parents in 'parent-folder' and mimeType = '{FOLDER_MIME}' and trashed=false")
    )


def test_list_folder_files_lists_non_folders_across_pages():
    service = _drive_with_pages([{"id": "doc-1", "name": "One"}], [{"id": "doc-2"}])
    with patch.object(google_drive, "_drive_service", return_value=service):
        result = google_drive.list_folder_files("parent-folder")

    assert result == [{"id": "doc-1", "name": "One"}, {"id": "doc-2", "name": None}]
    service.files.return_value.list.assert_called_once_with(
        **_list_kwargs(f"parents in 'parent-folder' and mimeType != '{FOLDER_MIME}' and trashed=false")
    )


def test_create_folder_creates_a_folder_in_the_parent_on_shared_drives():
    service = MagicMock()
    service.files.return_value.create.return_value.execute.return_value = {"id": "folder-new", "name": "Incident"}
    with patch.object(google_drive, "_drive_service", return_value=service):
        result = google_drive.create_folder("Incident", "parent-folder")

    assert result == {"id": "folder-new", "name": "Incident"}
    service.files.return_value.create.assert_called_once_with(
        body={"name": "Incident", "parents": ["parent-folder"], "mimeType": FOLDER_MIME}, supportsAllDrives=True
    )


def test_create_document_from_template_copies_the_template_into_the_parent():
    service = MagicMock()
    service.files.return_value.copy.return_value.execute.return_value = {"id": "doc-new", "name": "Report"}
    with patch.object(google_drive, "_drive_service", return_value=service):
        result = google_drive.create_document_from_template("Report", "parent-folder", "template-1")

    assert result == {"id": "doc-new", "name": "Report"}
    service.files.return_value.copy.assert_called_once_with(
        fileId="template-1", body={"name": "Report", "parents": ["parent-folder"]}, supportsAllDrives=True
    )


def test_find_document_by_channel_name_enriches_match_with_app_properties():
    service = _drive_with_pages([{"id": "doc-1", "name": "incident-2024-001"}])
    files_resource = service.files.return_value
    files_resource.get.return_value.execute.return_value = {
        "id": "doc-1",
        "name": "incident-2024-001",
        "appProperties": {"ic_id": "ic-1", "ol_id": "ol-1"},
    }
    with patch.object(google_drive, "_drive_service", return_value=service):
        result = google_drive.find_document_by_channel_name("2024-001")

    assert result == {"id": "doc-1", "appProperties": {"ic_id": "ic-1", "ol_id": "ol-1"}}
    files_resource.list.assert_called_once_with(**_list_kwargs("trashed=false and name='2024-001'"))
    files_resource.get.assert_called_once_with(fileId="doc-1", fields="id, name, appProperties", supportsAllDrives=True)


def test_find_document_by_channel_name_without_a_match_is_none():
    service = _drive_with_pages([])
    with patch.object(google_drive, "_drive_service", return_value=service):
        assert google_drive.find_document_by_channel_name("2024-001") is None


@pytest.mark.parametrize(
    ("status", "classified"),
    [(404, "NOT_FOUND"), (403, "UNAUTHORIZED"), (401, "UNAUTHORIZED"), (429, "TRANSIENT_ERROR"), (503, "TRANSIENT_ERROR")],
)
@pytest.mark.parametrize(
    ("call", "event", "empty"),
    [
        (lambda: google_drive.list_folder_files("p"), "incident_drive_list_files_failed", []),
        (lambda: google_drive.list_child_folders("p"), "incident_drive_list_folders_failed", []),
        (lambda: google_drive.create_folder("n", "p"), "incident_drive_create_folder_failed", None),
        (lambda: google_drive.create_document_from_template("n", "p", "t"), "incident_drive_create_document_failed", None),
        (lambda: google_drive.find_document_by_channel_name("n"), "incident_drive_find_document_failed", None),
    ],
)
def test_a_classified_drive_error_is_logged_and_returns_the_empty_value(status, classified, call, event, empty):
    """A refusal is logged by operation and by incident event, as the Drive provider did, and returns the empty value."""
    service = MagicMock()
    files = service.files.return_value
    for method in (files.list, files.create, files.copy):
        method.return_value.execute.side_effect = _http_error(status)
    with patch.object(google_drive, "_drive_service", return_value=service), capture_logs() as logs:
        assert call() == empty

    events = [entry["event"] for entry in logs]
    assert events == ["google_drive_operation_failed", event]
    assert logs[1]["status"] == OperationStatus[classified].value
    assert logs[1]["error_code"] == str(status)


def test_an_unclassified_drive_error_raises():
    """A status the gateway does not classify (400) is a defect and propagates, as it did through the provider."""
    service = MagicMock()
    service.files.return_value.list.return_value.execute.side_effect = _http_error(400)
    with patch.object(google_drive, "_drive_service", return_value=service), pytest.raises(HttpError):
        google_drive.list_folder_files("p")


def test_incident_drive_healthcheck_returns_false_when_metadata_lookup_raises():
    with patch.object(google_drive, "get_metadata", side_effect=RuntimeError("drive down")):
        assert google_drive.incident_drive_healthcheck() is False


def test_add_metadata_returns_updated_file_on_success():
    """add_metadata calls files().update() with appProperties and returns the updated file."""
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
