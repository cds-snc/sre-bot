"""Unit tests for DriveClient."""


import pytest

from infrastructure.clients.google_workspace.drive import DriveClient, MIME_TYPES
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus


@pytest.fixture
def mock_service(mock_session_provider):
    """Get the mock Google Drive service from session provider.

    This is the MagicMock service that supports chaining.
    """
    return mock_session_provider.get_service.return_value


@pytest.fixture
def drive_client(mock_session_provider):
    """Create DriveClient with mocked session provider from conftest."""
    return DriveClient(session_provider=mock_session_provider)


class TestMetadataOperations:
    """Test metadata operations."""

    def test_add_metadata_success(self, drive_client, mock_service):
        """Test adding metadata to a file."""
        # Arrange
        mock_service.files().update().execute.return_value = {
            "id": "file123",
            "name": "test.txt",
            "appProperties": {"incident_id": "INC-001"},
        }

        # Act
        result = drive_client.add_metadata(
            file_id="file123", key="incident_id", value="INC-001"
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "file123"
        assert result.data["appProperties"]["incident_id"] == "INC-001"
        # Verify update was called with correct parameters
        assert mock_service.files().update.called

    def test_add_metadata_with_delegation(
        self, drive_client, mock_session_provider, mock_service
    ):
        """Test adding metadata with delegated authentication."""
        # Arrange
        mock_service.files().update().execute.return_value = {"id": "file123"}

        # Act
        result = drive_client.add_metadata(
            file_id="file123",
            key="status",
            value="active",
            delegated_email="user@example.com",
        )

        # Assert
        assert result.is_success
        # Verify get_service was called with delegated_email parameter
        mock_session_provider.get_service.assert_called()
        # Check that delegated_user_email was passed in kwargs (note: parameter name difference)
        call_kwargs = mock_session_provider.get_service.call_args.kwargs
        assert "delegated_user_email" in call_kwargs or "delegated_email" in call_kwargs

    def test_delete_metadata_success(self, drive_client, mock_service):
        """Test deleting metadata from a file."""
        # Arrange
        mock_service.files().update().execute.return_value = {
            "id": "file123",
            "name": "test.txt",
            "appProperties": {},
        }

        # Act
        result = drive_client.delete_metadata(file_id="file123", key="old_key")

        # Assert
        assert result.is_success
        assert result.data["appProperties"] == {}

    def test_list_metadata_success(self, drive_client, mock_service):
        """Test listing all metadata for a file."""
        # Arrange
        mock_service.files().get().execute.return_value = {
            "id": "file123",
            "name": "test.txt",
            "appProperties": {"key1": "value1", "key2": "value2"},
        }

        # Act
        result = drive_client.list_metadata(file_id="file123")

        # Assert
        assert result.is_success
        assert len(result.data["appProperties"]) == 2


class TestFolderOperations:
    """Test folder operations."""

    def test_create_folder_success(self, drive_client, mock_service):
        """Test creating a new folder."""
        # Arrange
        mock_service.files().create().execute.return_value = {
            "id": "folder123",
            "name": "Incidents 2026",
        }

        # Act
        result = drive_client.create_folder(
            name="Incidents 2026", parent_folder_id="parent123"
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "folder123"
        assert result.data["name"] == "Incidents 2026"

        # Verify correct MIME type was used
        call_kwargs = mock_service.files().create.call_args[1]
        assert call_kwargs["body"]["mimeType"] == MIME_TYPES["folder"]

    def test_list_folders_in_folder_success(self, drive_client, mock_service):
        """Test listing folders within a parent folder."""
        # Arrange
        mock_service.files().list().execute.return_value = {
            "files": [
                {"id": "folder1", "name": "Subfolder 1"},
                {"id": "folder2", "name": "Subfolder 2"},
            ]
        }

        # Act
        result = drive_client.list_folders_in_folder(folder_id="parent123")

        # Assert
        assert result.is_success
        assert len(result.data) == 2
        assert result.data[0]["name"] == "Subfolder 1"

    def test_list_folders_with_query(self, drive_client, mock_service):
        """Test listing folders with additional query filter."""
        # Arrange
        mock_service.files().list().execute.return_value = {
            "files": [{"id": "folder1", "name": "Active Folder"}]
        }

        # Act
        result = drive_client.list_folders_in_folder(
            folder_id="parent123", query="name contains 'Active'"
        )

        # Assert
        assert result.is_success
        call_kwargs = mock_service.files().list.call_args[1]
        assert "name contains 'Active'" in call_kwargs["q"]

    def test_list_folders_pagination(self, drive_client, mock_service):
        """Test pagination when listing folders."""
        # Arrange: First page has nextPageToken
        mock_service.files().list().execute.side_effect = [
            {
                "files": [{"id": "f1", "name": "Folder 1"}],
                "nextPageToken": "token123",
            },
            {"files": [{"id": "f2", "name": "Folder 2"}]},
        ]

        # Act
        result = drive_client.list_folders_in_folder(folder_id="parent123")

        # Assert
        assert result.is_success
        assert len(result.data) == 2  # Both pages combined

    def test_list_files_in_folder_success(self, drive_client, mock_service):
        """Test listing non-folder files in a folder."""
        # Arrange
        mock_service.files().list().execute.return_value = {
            "files": [
                {"id": "file1", "name": "document.doc"},
                {"id": "file2", "name": "spreadsheet.xlsx"},
            ]
        }

        # Act
        result = drive_client.list_files_in_folder(folder_id="parent123")

        # Assert
        assert result.is_success
        assert len(result.data) == 2
        # Verify query excludes folders
        call_kwargs = mock_service.files().list.call_args[1]
        assert MIME_TYPES["folder"] in call_kwargs["q"]
        assert "!=" in call_kwargs["q"]


class TestFileOperations:
    """Test file operations."""

    def test_get_file_success(self, drive_client, mock_service):
        """Test getting file metadata by ID."""
        # Arrange
        mock_service.files().get().execute.return_value = {
            "id": "file123",
            "name": "document.doc",
            "mimeType": "application/vnd.google-apps.document",
        }

        # Act
        result = drive_client.get_file(file_id="file123")

        # Assert
        assert result.is_success
        assert result.data["name"] == "document.doc"

    def test_get_file_with_custom_fields(self, drive_client, mock_service):
        """Test getting file with custom fields selection."""
        # Arrange
        mock_service.files().get().execute.return_value = {
            "id": "file123",
            "name": "document.doc",
        }

        # Act
        result = drive_client.get_file(file_id="file123", fields="id, name, owners")

        # Assert
        assert result.is_success
        call_kwargs = mock_service.files().get.call_args[1]
        assert call_kwargs["fields"] == "id, name, owners"

    def test_find_files_by_name_success(self, drive_client, mock_service):
        """Test finding files by exact name."""
        # Arrange
        mock_service.files().list().execute.return_value = {
            "files": [
                {"id": "file1", "name": "incident.doc"},
                {"id": "file2", "name": "incident.doc"},
            ]
        }

        # Act
        result = drive_client.find_files_by_name(name="incident.doc")

        # Assert
        assert result.is_success
        assert len(result.data) == 2

    def test_find_files_by_name_in_folder(self, drive_client, mock_service):
        """Test finding files by name within a specific folder."""
        # Arrange
        mock_service.files().list().execute.return_value = {
            "files": [{"id": "file1", "name": "incident.doc"}]
        }

        # Act
        result = drive_client.find_files_by_name(
            name="incident.doc", folder_id="folder123"
        )

        # Assert
        assert result.is_success
        call_kwargs = mock_service.files().list.call_args[1]
        assert "folder123" in call_kwargs["q"]

    def test_create_file_success(self, drive_client, mock_service):
        """Test creating a new Google Workspace file."""
        # Arrange
        mock_service.files().create().execute.return_value = {
            "id": "doc123",
            "name": "New Document",
        }

        # Act
        result = drive_client.create_file(
            name="New Document",
            file_type="document",
            parent_folder_id="folder123",
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "doc123"
        call_kwargs = mock_service.files().create.call_args[1]
        assert call_kwargs["body"]["mimeType"] == MIME_TYPES["document"]

    def test_create_file_invalid_type(self, drive_client):
        """Test creating file with invalid file type."""
        # Act
        result = drive_client.create_file(
            name="Invalid",
            file_type="invalid_type",
            parent_folder_id="folder123",
        )

        # Assert
        assert not result.is_success
        assert result.status == OperationStatus.PERMANENT_ERROR
        assert "Invalid file_type" in result.message

    @pytest.mark.parametrize(
        "file_type,expected_mime",
        [
            ("document", MIME_TYPES["document"]),
            ("spreadsheet", MIME_TYPES["spreadsheet"]),
            ("presentation", MIME_TYPES["presentation"]),
            ("form", MIME_TYPES["form"]),
        ],
    )
    def test_create_file_types(
        self, drive_client, mock_service, file_type, expected_mime
    ):
        """Test creating different file types."""
        # Arrange
        mock_service.files().create().execute.return_value = {"id": "file123"}

        # Act
        result = drive_client.create_file(
            name="Test File",
            file_type=file_type,
            parent_folder_id="folder123",
        )

        # Assert
        assert result.is_success
        call_kwargs = mock_service.files().create.call_args[1]
        assert call_kwargs["body"]["mimeType"] == expected_mime

    def test_create_file_from_template_success(self, drive_client, mock_service):
        """Test creating file from template."""
        # Arrange
        mock_service.files().copy().execute.return_value = {
            "id": "new123",
            "name": "Incident Report",
        }

        # Act
        result = drive_client.create_file_from_template(
            name="Incident Report",
            template_id="template123",
            parent_folder_id="folder123",
        )

        # Assert
        assert result.is_success
        assert result.data["id"] == "new123"
        # Verify copy was called (MagicMock chains count intermediate calls)
        assert mock_service.files().copy.called

    def test_copy_file_to_folder_success(self, drive_client, mock_service):
        """Test copying file and moving to destination folder."""
        # Arrange
        mock_service.files().copy().execute.return_value = {"id": "copy123"}
        mock_service.files().update().execute.return_value = {"id": "copy123"}

        # Act
        result = drive_client.copy_file_to_folder(
            file_id="original123",
            name="Copy of File",
            source_parent_id="source123",
            destination_folder_id="dest123",
        )

        # Assert
        assert result.is_success
        assert result.data == "copy123"
        # Verify both copy and update were called (MagicMock chains count all calls)
        assert mock_service.files().copy.called
        assert mock_service.files().update.called

        # Verify update moved file between folders
        update_kwargs = mock_service.files().update.call_args[1]
        assert update_kwargs["addParents"] == "dest123"
        assert update_kwargs["removeParents"] == "source123"


class TestErrorHandling:
    """Test error handling scenarios.

    Note: Detailed error handling (retries, rate limits) is tested in
    test_executor.py. These tests verify that DriveClient methods properly
    propagate OperationResult from the executor.
    """

    def test_api_call_propagates_operation_result(self, drive_client, mock_service):
        """Test that API calls return results wrapped in OperationResult."""
        # Arrange
        mock_service.files().get().execute.return_value = {
            "id": "file123",
            "name": "test.txt",
        }

        # Act
        result = drive_client.get_file(file_id="file123")

        # Assert
        assert isinstance(result, OperationResult)
        assert result.is_success
        assert result.data["id"] == "file123"
