"""Drive client for Google Workspace operations.

Provides type-safe access to Google Drive API (files, folders, permissions, metadata).
All methods return OperationResult for consistent error handling.
"""

from typing import TYPE_CHECKING, Any, Optional

import structlog

from infrastructure.clients.google_workspace.executor import execute_google_api_call
from infrastructure.operations.result import OperationResult

if TYPE_CHECKING:
    from infrastructure.clients.google_workspace.session_provider import (
        SessionProvider,
    )

logger = structlog.get_logger()

# Drive API scopes
DRIVE_FULL_SCOPE = "https://www.googleapis.com/auth/drive"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_METADATA_SCOPE = "https://www.googleapis.com/auth/drive.metadata"

# MIME types for Google Workspace files
MIME_TYPES = {
    "folder": "application/vnd.google-apps.folder",
    "document": "application/vnd.google-apps.document",
    "spreadsheet": "application/vnd.google-apps.spreadsheet",
    "presentation": "application/vnd.google-apps.presentation",
    "form": "application/vnd.google-apps.form",
    "site": "application/vnd.google-apps.site",
}


class DriveClient:
    """Client for Google Drive API operations.

    Handles files, folders, permissions, and metadata operations.
    Thread safety: Not thread-safe. Create one instance per thread.

    Args:
        session_provider: SessionProvider for authentication and service creation

    Usage:
        # Get file by ID
        result = drive_client.get_file(file_id="abc123")
        if result.is_success:
            file = result.data
            logger.info("file_retrieved", file_id=file["id"])

        # Create folder
        result = drive_client.create_folder(
            name="Incidents 2026",
            parent_folder_id="xyz789"
        )
    """

    def __init__(self, session_provider: "SessionProvider") -> None:
        """Initialize Drive client.

        Args:
            session_provider: SessionProvider instance for API authentication
        """
        self._session_provider = session_provider
        self._logger = logger.bind(client="drive")

    # ========================================================================
    # File Metadata Operations
    # ========================================================================

    def add_metadata(
        self,
        file_id: str,
        key: str,
        value: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Add custom metadata to a file using appProperties.

        Args:
            file_id: File ID to add metadata to
            key: Metadata key
            value: Metadata value
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with updated file metadata containing name and appProperties
        """
        self._logger.info(
            "adding_metadata",
            file_id=file_id,
            key=key,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.files()
                .update(
                    fileId=file_id,
                    body={"appProperties": {key: value}},
                    fields="id, name, appProperties",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="drive.files.update_metadata",
            api_callable=api_call,
        )

    def delete_metadata(
        self,
        file_id: str,
        key: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Delete custom metadata from a file by setting key to None.

        Args:
            file_id: File ID to delete metadata from
            key: Metadata key to delete
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with updated file metadata
        """
        self._logger.info(
            "deleting_metadata",
            file_id=file_id,
            key=key,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.files()
                .update(
                    fileId=file_id,
                    body={"appProperties": {key: None}},
                    fields="id, name, appProperties",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="drive.files.delete_metadata",
            api_callable=api_call,
        )

    def list_metadata(
        self,
        file_id: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get all custom metadata for a file.

        Args:
            file_id: File ID to retrieve metadata from
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with file metadata including appProperties
        """
        self._logger.debug(
            "listing_metadata", file_id=file_id, delegated_user_email=delegated_email
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.files()
                .get(
                    fileId=file_id,
                    fields="id, name, appProperties",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="drive.files.get_metadata",
            api_callable=api_call,
        )

    # ========================================================================
    # Folder Operations
    # ========================================================================

    def create_folder(
        self,
        name: str,
        parent_folder_id: str,
        fields: Optional[str] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a new folder in Google Drive.

        Args:
            name: Name of the new folder
            parent_folder_id: Parent folder ID
            fields: Optional fields to include in response (default: "id, name")
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with File resource representing the new folder
        """
        self._logger.info(
            "creating_folder",
            name=name,
            parent_folder_id=parent_folder_id,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.files()
                .create(
                    body={
                        "name": name,
                        "parents": [parent_folder_id],
                        "mimeType": MIME_TYPES["folder"],
                    },
                    fields=fields or "id, name",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="drive.folders.create",
            api_callable=api_call,
        )

    def list_folders_in_folder(
        self,
        folder_id: str,
        query: Optional[str] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """List all folders within a parent folder.

        Args:
            folder_id: Parent folder ID to list from
            query: Optional additional query filter
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with list of folders (id, name)
        """
        self._logger.debug(
            "listing_folders",
            folder_id=folder_id,
            query=query,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        base_query = f"parents in '{folder_id}' and mimeType = '{MIME_TYPES['folder']}' and trashed=false"
        if query:
            base_query += f" and {query}"

        def api_call() -> Any:
            all_folders = []
            page_token = None

            while True:
                response = (
                    service.files()
                    .list(
                        q=base_query,
                        pageSize=100,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name)",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora="user",
                    )
                    .execute()
                )

                all_folders.extend(response.get("files", []))
                page_token = response.get("nextPageToken")

                if not page_token:
                    break

            return all_folders

        return execute_google_api_call(
            operation_name="drive.folders.list",
            api_callable=api_call,
        )

    def list_files_in_folder(
        self,
        folder_id: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """List all non-folder files within a parent folder.

        Args:
            folder_id: Parent folder ID to list from
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with list of files (id, name)
        """
        self._logger.debug(
            "listing_files", folder_id=folder_id, delegated_user_email=delegated_email
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        query = f"parents in '{folder_id}' and mimeType != '{MIME_TYPES['folder']}' and trashed=false"

        def api_call() -> Any:
            all_files = []
            page_token = None

            while True:
                response = (
                    service.files()
                    .list(
                        q=query,
                        pageSize=100,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name)",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora="user",
                    )
                    .execute()
                )

                all_files.extend(response.get("files", []))
                page_token = response.get("nextPageToken")

                if not page_token:
                    break

            return all_files

        return execute_google_api_call(
            operation_name="drive.files.list",
            api_callable=api_call,
        )

    # ========================================================================
    # File Operations
    # ========================================================================

    def get_file(
        self,
        file_id: str,
        fields: Optional[str] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Get file metadata by ID.

        Args:
            file_id: File ID to retrieve
            fields: Optional fields to include in response
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with file metadata
        """
        self._logger.debug(
            "getting_file", file_id=file_id, delegated_user_email=delegated_email
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.files()
                .get(
                    fileId=file_id,
                    fields=fields or "id, name, mimeType, createdTime, modifiedTime",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="drive.files.get",
            api_callable=api_call,
        )

    def find_files_by_name(
        self,
        name: str,
        folder_id: Optional[str] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Find files by name, optionally within a specific folder.

        Args:
            name: File name to search for (exact match)
            folder_id: Optional folder ID to limit search scope
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with list of matching files
        """
        self._logger.debug(
            "finding_files",
            name=name,
            folder_id=folder_id,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        query = f"trashed=false and name='{name}'"
        if folder_id:
            query += f" and '{folder_id}' in parents"

        def api_call() -> Any:
            all_files = []
            page_token = None

            while True:
                response = (
                    service.files()
                    .list(
                        q=query,
                        pageSize=100,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name, appProperties)",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                        corpora="user",
                    )
                    .execute()
                )

                all_files.extend(response.get("files", []))
                page_token = response.get("nextPageToken")

                if not page_token:
                    break

            return all_files

        return execute_google_api_call(
            operation_name="drive.files.find_by_name",
            api_callable=api_call,
        )

    def create_file(
        self,
        name: str,
        file_type: str,
        parent_folder_id: str,
        fields: Optional[str] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a new Google Workspace file (Doc, Sheet, Slide, Form, Site).

        Args:
            name: Name of the new file
            file_type: Type of file ("document", "spreadsheet", "presentation", "form", "site")
            parent_folder_id: Parent folder ID
            fields: Optional fields to include in response (default: "id, name")
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with File resource representing the new file

        Raises:
            ValueError: If file_type is invalid
        """
        if file_type not in MIME_TYPES:
            return OperationResult.permanent_error(
                message=f"Invalid file_type: {file_type}. Must be one of: {list(MIME_TYPES.keys())}",
                error_code="INVALID_FILE_TYPE",
            )

        self._logger.info(
            "creating_file",
            name=name,
            file_type=file_type,
            parent_folder_id=parent_folder_id,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.files()
                .create(
                    body={
                        "name": name,
                        "parents": [parent_folder_id],
                        "mimeType": MIME_TYPES[file_type],
                    },
                    fields=fields or "id, name",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="drive.files.create",
            api_callable=api_call,
        )

    def create_file_from_template(
        self,
        name: str,
        template_id: str,
        parent_folder_id: str,
        fields: Optional[str] = None,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Create a new file by copying a template.

        Works for Docs, Sheets, Slides, Forms, Sites.

        Args:
            name: Name of the new file
            template_id: Template file ID to copy from
            parent_folder_id: Parent folder ID for the new file
            fields: Optional fields to include in response (default: "id, name")
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with File resource representing the new file
        """
        self._logger.info(
            "creating_from_template",
            name=name,
            template_id=template_id,
            parent_folder_id=parent_folder_id,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            return (
                service.files()
                .copy(
                    fileId=template_id,
                    body={"name": name, "parents": [parent_folder_id]},
                    fields=fields or "id, name",
                    supportsAllDrives=True,
                )
                .execute()
            )

        return execute_google_api_call(
            operation_name="drive.files.copy_template",
            api_callable=api_call,
        )

    def copy_file_to_folder(
        self,
        file_id: str,
        name: str,
        source_parent_id: str,
        destination_folder_id: str,
        delegated_email: Optional[str] = None,
    ) -> OperationResult:
        """Copy a file and move the copy to a destination folder.

        This is a two-step operation:
        1. Copy the file to the source parent
        2. Move the copy to the destination folder

        Args:
            file_id: File ID to copy
            name: Name for the copied file
            source_parent_id: Initial parent folder for the copy
            destination_folder_id: Final destination folder
            delegated_email: Optional email to delegate authentication to

        Returns:
            OperationResult with the file ID of the final copied file
        """
        self._logger.info(
            "copying_file_to_folder",
            file_id=file_id,
            name=name,
            destination_folder_id=destination_folder_id,
            delegated_user_email=delegated_email,
        )

        service = self._session_provider.get_service(
            service_name="drive",
            version="v3",
            scopes=[DRIVE_FULL_SCOPE],
            delegated_user_email=delegated_email,
        )

        def api_call() -> Any:
            # Step 1: Copy file
            copied_file = (
                service.files()
                .copy(
                    fileId=file_id,
                    body={"name": name, "parents": [source_parent_id]},
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )
            copied_file_id = copied_file["id"]

            # Step 2: Move copy to destination
            updated_file = (
                service.files()
                .update(
                    fileId=copied_file_id,
                    addParents=destination_folder_id,
                    removeParents=source_parent_id,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )

            return updated_file["id"]

        return execute_google_api_call(
            operation_name="drive.files.copy_and_move",
            api_callable=api_call,
        )
