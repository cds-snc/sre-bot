"""Google Workspace implementation of the DriveProvider contract."""

from collections.abc import Callable
from typing import Any

from googleapiclient.errors import HttpError

from infrastructure.drive.models import DriveFile
from infrastructure.drive.settings import DriveSettings
from infrastructure.operations import OperationResult
from integrations.google_workspace.client import classify_google_error

_DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
_FILE_FIELDS = "nextPageToken, files(id, name, mimeType, parents, appProperties)"


class GoogleDriveProvider:
    """DriveProvider backed by the Google Drive API."""

    def __init__(
        self,
        get_service: Callable[[list[str], str | None], Any],
        drive_settings: DriveSettings,
    ) -> None:
        self._get_service = get_service
        self._drive_settings = drive_settings

    def _call(self, operation: str, fn: Callable[[], Any]) -> OperationResult[Any]:
        try:
            return OperationResult.success(data=fn(), provider="google", operation=operation)
        except HttpError as exc:
            status, error_code, retry_after = classify_google_error(exc)
            return OperationResult.error(
                status=status,
                message=str(exc),
                error_code=error_code,
                retry_after=retry_after,
                provider="google",
                operation=operation,
            )

    def _build_file(self, payload: dict[str, Any]) -> DriveFile:
        raw_properties = payload.get("appProperties")
        app_properties = raw_properties if isinstance(raw_properties, dict) else {}
        return DriveFile(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            mime_type=str(payload.get("mimeType") or "") or None,
            parents=tuple(str(parent) for parent in payload.get("parents", []) if parent),
            app_properties={str(key): str(value) for key, value in app_properties.items() if value is not None},
            provider="google",
        )

    def _list(self, parent_id: str, mime_query: str, operation: str) -> OperationResult[list[DriveFile]]:
        def run() -> list[DriveFile]:
            files_resource = self._get_service([_DRIVE_SCOPE], None).files()
            request = files_resource.list(
                q=f"'{parent_id}' in parents and {mime_query} and trashed=false",
                fields=_FILE_FIELDS,
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="user",
            )
            files: list[DriveFile] = []
            while request is not None:
                response = request.execute()
                files.extend(self._build_file(item) for item in response.get("files", []) if isinstance(item, dict))
                request = files_resource.list_next(request, response)
            return files

        return self._call(operation, run)

    def list_files(self, parent_id: str) -> OperationResult[list[DriveFile]]:
        """List non-folder files directly within a parent folder."""
        return self._list(parent_id, f"mimeType != '{_FOLDER_MIME_TYPE}'", "list_files")

    def list_folders(self, parent_id: str) -> OperationResult[list[DriveFile]]:
        """List folders directly within a parent folder."""
        return self._list(parent_id, f"mimeType = '{_FOLDER_MIME_TYPE}'", "list_folders")

    def copy_file_to_folder(
        self,
        source_file_id: str,
        name: str,
        source_parent_id: str,
        destination_folder_id: str,
    ) -> OperationResult[DriveFile]:
        """Copy a file then move the copy into the destination folder."""

        def run() -> DriveFile:
            files_resource = self._get_service([_DRIVE_SCOPE], None).files()
            copied = files_resource.copy(
                fileId=source_file_id,
                body={"name": name, "parents": [source_parent_id]},
                supportsAllDrives=True,
                fields="id, name, mimeType, parents, appProperties",
            ).execute()
            moved = files_resource.update(
                fileId=copied["id"],
                body={},
                addParents=destination_folder_id,
                removeParents=source_parent_id,
                supportsAllDrives=True,
                fields="id, name, mimeType, parents, appProperties",
            ).execute()
            return self._build_file(moved)

        return self._call("copy_file_to_folder", run)
