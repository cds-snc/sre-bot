from unittest.mock import MagicMock, patch

from infrastructure.drive.models import DriveFile
from infrastructure.operations import OperationResult


@patch("packages.talent.adapters.google_drive.get_drive_provider")
def test_create_role_folder_success(mock_get_provider):
    from packages.talent.adapters import google_drive

    provider = MagicMock()
    provider.create_folder.return_value = OperationResult.success(data=DriveFile(id="folder-1", name="Alpha"))
    mock_get_provider.return_value = provider

    result = google_drive.create_role_folder("Alpha", "parent-folder")

    assert result == {"id": "folder-1", "name": "Alpha"}
    provider.create_folder.assert_called_once_with(
        "Alpha",
        "parent-folder",
        delegated_user_email=google_drive.BOT_EMAIL,
    )


@patch("packages.talent.adapters.google_drive.get_drive_provider")
def test_create_role_folder_failure_returns_none(mock_get_provider):
    from packages.talent.adapters import google_drive

    provider = MagicMock()
    provider.create_folder.return_value = OperationResult.permanent_error(
        "folder failed",
        error_code="drive_error",
    )
    mock_get_provider.return_value = provider

    assert google_drive.create_role_folder("Alpha", "parent-folder") is None


@patch("packages.talent.adapters.google_drive.get_drive_provider")
def test_copy_template_to_role_folder_success(mock_get_provider):
    from packages.talent.adapters import google_drive

    provider = MagicMock()
    provider.copy_file_to_folder.return_value = OperationResult.success(data=DriveFile(id="copy-1", name="copy-name"))
    mock_get_provider.return_value = provider

    result = google_drive.copy_template_to_role_folder(
        "template-1",
        "Candidate doc",
        "templates-folder",
        "folder-1",
    )

    assert result == "copy-1"
    provider.copy_file_to_folder.assert_called_once_with(
        "template-1",
        "Candidate doc",
        "templates-folder",
        "folder-1",
        delegated_user_email=google_drive.BOT_EMAIL,
    )


@patch("packages.talent.adapters.google_drive.get_drive_provider")
def test_copy_template_to_role_folder_failure_returns_none(mock_get_provider):
    from packages.talent.adapters import google_drive

    provider = MagicMock()
    provider.copy_file_to_folder.return_value = OperationResult.transient_error(
        "copy failed",
        error_code="drive_error",
        retry_after=30,
    )
    mock_get_provider.return_value = provider

    assert google_drive.copy_template_to_role_folder("template-1", "Candidate doc", "templates-folder", "folder-1") is None


@patch("packages.talent.adapters.google_drive.get_drive_provider")
def test_adapter_returns_none_when_provider_data_is_missing(mock_get_provider):
    from packages.talent.adapters import google_drive

    provider = MagicMock()
    provider.create_folder.return_value = OperationResult.success(data=None)
    provider.copy_file_to_folder.return_value = OperationResult.success(data=None)
    mock_get_provider.return_value = provider

    assert google_drive.create_role_folder("Alpha", "parent-folder") is None
    assert google_drive.copy_template_to_role_folder("template-1", "Candidate doc", "templates-folder", "folder-1") is None
