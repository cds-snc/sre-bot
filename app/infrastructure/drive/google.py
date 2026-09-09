"""Google Workspace implementation of the DriveProvider contract."""

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

import structlog
from googleapiclient.errors import HttpError

from infrastructure.drive.models import DriveFile
from infrastructure.drive.settings import DriveSettings
from infrastructure.operations import OperationResult
from integrations.google_workspace.client import classify_google_error
from integrations.google_workspace.google_drive import DRIVE_SCOPES

_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"

logger = structlog.get_logger()

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import DriveResource  # pyright: ignore[reportMissingModuleSource]


class GoogleDriveProvider:
    """DriveProvider backed by the Google Drive API."""

    def __init__(self, get_service: Callable[[list[str], str | None], DriveResource], drive_settings: DriveSettings) -> None:
        self._get_service = get_service
        self._drive_settings = drive_settings

    def _map_sdk_exception(self, exc: HttpError, operation: str) -> OperationResult[Any]:
        status, error_code, retry_after = classify_google_error(exc)
        return OperationResult.error(
            status=status,
            message=str(exc),
            error_code=error_code,
            retry_after=retry_after,
            provider="google",
            operation=operation,
        )

    def _call(self, operation: str, fn: Callable[[], Any]) -> OperationResult[Any]:
        try:
            return OperationResult.success(data=fn(), provider="google", operation=operation)
        except HttpError as exc:
            return self._map_sdk_exception(exc, operation)

    def _build_drive_file(self, payload: Mapping[str, Any]) -> DriveFile:
        raw_parents = payload.get("parents")
        parents = tuple(str(parent) for parent in raw_parents if parent) if isinstance(raw_parents, list) else ()
        return DriveFile(
            id=str(payload.get("id") or ""),
            name=str(payload["name"]) if payload.get("name") is not None else None,
            mime_type=str(payload["mimeType"]) if payload.get("mimeType") is not None else None,
            parents=parents,
            provider="google",
        )

    def _service(self, delegated_user_email: str | None) -> DriveResource:
        return self._get_service(DRIVE_SCOPES, delegated_user_email)

    def _collect_files(self, files_resource: Any, request: Any) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        while request is not None:
            response = request.execute()
            results.extend(item for item in response.get("files", []) if isinstance(item, dict))
            request = files_resource.list_next(request, response)
        return results

    def warmup(self) -> OperationResult[None]:
        """Validate Drive credentials with a minimal list request."""
        result = self._call(
            "warmup",
            lambda: self._service(None).files().list(pageSize=1, fields="files(id)").execute(),
        )
        if result.is_success:
            return OperationResult.success(provider="google", operation="warmup")
        return OperationResult.error(
            status=result.status,
            message=result.message,
            error_code=result.error_code,
            retry_after=result.retry_after,
            provider=result.provider,
            operation=result.operation,
        )

    def health_check(self) -> OperationResult[None]:
        """Return local liveness without making a Drive API call."""
        return OperationResult.success(provider="google", operation="health_check")

    def create_folder(
        self, name: str, parent_folder_id: str, *, fields: str | None = None, delegated_user_email: str | None = None
    ) -> OperationResult[DriveFile]:
        return self._create(
            "create_folder",
            lambda files: files.create(
                body={"name": name, "parents": [parent_folder_id], "mimeType": _FOLDER_MIME_TYPE},
                supportsAllDrives=True,
                fields=fields,
            ),
            delegated_user_email,
        )

    def _create(
        self, operation: str, request_factory: Callable[[Any], Any], delegated_user_email: str | None
    ) -> OperationResult[DriveFile]:
        return self._call(
            operation,
            lambda: self._build_drive_file(request_factory(self._service(delegated_user_email).files()).execute()),
        )

    def _list(
        self, query: str, fields: str | None, operation: str, delegated_user_email: str | None
    ) -> OperationResult[list[DriveFile]]:
        def run() -> list[DriveFile]:
            files = self._service(delegated_user_email).files()
            request = files.list(
                q=query,
                fields=fields,
                pageSize=100,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="user",
            )
            return [self._build_drive_file(item) for item in self._collect_files(files, request)]

        return self._call(operation, run)

    def list_folders(
        self,
        parent_folder_id: str,
        query: str | None = None,
        *,
        fields: str | None = None,
        delegated_user_email: str | None = None,
    ) -> OperationResult[list[DriveFile]]:
        drive_query = f"parents in '{parent_folder_id}' and mimeType = '{_FOLDER_MIME_TYPE}' and trashed=false"
        if query:
            drive_query += f" and {query}"
        return self._list(drive_query, fields, "list_folders", delegated_user_email)

    def list_files(
        self, parent_folder_id: str, *, fields: str | None = None, delegated_user_email: str | None = None
    ) -> OperationResult[list[DriveFile]]:
        return self._list(
            f"parents in '{parent_folder_id}' and mimeType != '{_FOLDER_MIME_TYPE}' and trashed=false",
            fields,
            "list_files",
            delegated_user_email,
        )

    def find_files_by_name(
        self,
        name: str,
        parent_folder_id: str | None = None,
        *,
        fields: str | None = None,
        delegated_user_email: str | None = None,
    ) -> OperationResult[list[DriveFile]]:
        query = f"trashed=false and name='{name}'"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"
        return self._list(query, fields, "find_files_by_name", delegated_user_email)

    def create_file_from_template(
        self,
        name: str,
        parent_folder_id: str,
        template_id: str,
        *,
        fields: str | None = None,
        delegated_user_email: str | None = None,
    ) -> OperationResult[DriveFile]:
        return self._create(
            "create_file_from_template",
            lambda files: files.copy(
                fileId=template_id,
                body={"name": name, "parents": [parent_folder_id]},
                supportsAllDrives=True,
                fields=fields,
            ),
            delegated_user_email,
        )

    def copy_file_to_folder(
        self,
        file_id: str,
        name: str,
        source_parent_id: str,
        destination_folder_id: str,
        *,
        delegated_user_email: str | None = None,
    ) -> OperationResult[DriveFile]:
        def run() -> DriveFile:
            files = self._service(delegated_user_email).files()
            copied = files.copy(
                fileId=file_id,
                body={"name": name, "parents": [source_parent_id]},
                supportsAllDrives=True,
                fields="id",
            ).execute()
            logger.debug("google_drive_file_copied", file_id=copied["id"])
            moved = files.update(
                fileId=copied["id"],
                body={},
                addParents=destination_folder_id,
                removeParents=source_parent_id,
                supportsAllDrives=True,
                fields="id",
            ).execute()
            logger.debug("google_drive_file_moved", file_id=moved["id"])
            return self._build_drive_file(moved)

        return self._call("copy_file_to_folder", run)
