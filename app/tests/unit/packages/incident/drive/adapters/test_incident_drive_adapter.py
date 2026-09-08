from unittest.mock import MagicMock, patch

from infrastructure.drive.models import DriveFile
from infrastructure.operations import OperationResult


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

    with patch.object(google_drive, "get_legacy_google_drive", return_value=MagicMock()) as mock_legacy:
        mock_legacy.return_value.list_metadata.return_value = {
            "id": "doc-1",
            "name": "incident-2024-001",
            "appProperties": {"ic_id": "ic-1", "ol_id": "ol-1"},
        }

        result = google_drive.find_document_by_channel_name("2024-001")

    assert result == {"id": "doc-1", "appProperties": {"ic_id": "ic-1", "ol_id": "ol-1"}}
    provider.find_files_by_name.assert_called_once_with("2024-001")
    mock_legacy.return_value.list_metadata.assert_called_once_with("doc-1", fields="id, name, appProperties")


@patch("packages.incident.drive.adapters.google_drive.get_drive_provider")
def test_incident_drive_healthcheck_returns_false_when_legacy_lookup_raises(mock_get_provider):
    from packages.incident.drive.adapters import google_drive

    provider = MagicMock()
    mock_get_provider.return_value = provider

    with patch.object(google_drive, "get_metadata", side_effect=RuntimeError("drive down")):
        assert google_drive.incident_drive_healthcheck() is False
