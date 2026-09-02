"""Google Drive operations that add application-specific query composition."""

from typing import TYPE_CHECKING, Any, cast

import structlog

from infrastructure.configuration.integrations.google import get_google_resources_config
from integrations.google_workspace import client as google_service_client

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3 import File  # pyright: ignore[reportMissingModuleSource]

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
INCIDENT_TEMPLATE = get_google_resources_config().incident_template_id

logger = structlog.get_logger()


def _execute_file_request(request: Any) -> dict[str, Any]:
    return cast("dict[str, Any]", google_service_client.execute_google_api_request(request))


def _collect_files(files_resource: Any, request: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    while request is not None:
        response = _execute_file_request(request)
        results.extend(response.get("files", []))
        request = files_resource.list_next(request, response)
    return results


def add_metadata(
    file_id: str,
    key: str,
    value: str,
    *,
    fields: str | None = None,
    delegated_user_email: str | None = None,
) -> dict[str, Any]:
    """Add application metadata to a Drive file."""
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    body = cast("File", {"appProperties": {key: value}})
    return _execute_file_request(service.files().update(fileId=file_id, body=body, fields=fields, supportsAllDrives=True))


def delete_metadata(
    file_id: str,
    key: str,
    *,
    fields: str | None = None,
    delegated_user_email: str | None = None,
) -> dict[str, Any]:
    """Remove an application metadata key from a Drive file."""
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    body = cast("File", {"appProperties": {key: None}})
    return _execute_file_request(service.files().update(fileId=file_id, body=body, fields=fields, supportsAllDrives=True))


def list_metadata(
    file_id: str,
    *,
    fields: str | None = None,
    delegated_user_email: str | None = None,
) -> dict[str, Any]:
    """Get metadata for a Drive file."""
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    return _execute_file_request(service.files().get(fileId=file_id, fields=fields, supportsAllDrives=True))


def create_folder(
    name: str,
    parent_folder: str,
    fields: str | None = None,
    *,
    delegated_user_email: str | None = None,
) -> dict[str, Any]:
    """Create a folder in Google Drive."""
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    body = cast(
        "File",
        {"name": name, "parents": [parent_folder], "mimeType": "application/vnd.google-apps.folder"},
    )
    return _execute_file_request(service.files().create(body=body, supportsAllDrives=True, fields=fields))


def create_file_from_template(
    name: str,
    folder: str,
    template: str,
    fields: str | None = None,
    *,
    delegated_user_email: str | None = None,
) -> dict[str, Any]:
    """Create a Drive file by copying a template."""
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    body = cast("File", {"name": name, "parents": [folder]})
    return _execute_file_request(service.files().copy(fileId=template, body=body, supportsAllDrives=True, fields=fields))


def create_file(
    name: str,
    folder: str,
    file_type: str,
    *,
    fields: str | None = None,
    delegated_user_email: str | None = None,
) -> dict[str, Any]:
    """Create a new file in Google Drive. Options for 'file_type' are: "document": Google Docs, "spreadsheet": Google Sheets, "presentation": Google Slides, "form": Google Forms, "site": Google Sites

    Args:
        name (str): The name of the new file.
        folder (str): The id of the folder to create the file in.
        file_type (str): The type of the new file.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        str: The id of the new file.
    """

    mime_type = {
        "document": "application/vnd.google-apps.document",
        "spreadsheet": "application/vnd.google-apps.spreadsheet",
        "presentation": "application/vnd.google-apps.presentation",
        "form": "application/vnd.google-apps.form",
        "site": "application/vnd.google-apps.site",
    }

    if file_type not in mime_type:
        raise ValueError(f"Invalid file_type: {file_type}")

    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    body = cast("File", {"name": name, "parents": [folder], "mimeType": mime_type[file_type]})
    return _execute_file_request(service.files().create(body=body, supportsAllDrives=True, fields=fields))


def find_files_by_name(
    name: str,
    folder_id: str | None = None,
    *,
    fields: str | None = None,
    pageSize: int = 100,
    delegated_user_email: str | None = None,
) -> list[dict[str, Any]]:
    """Get a file by name in a specific Google Drive folder.

    This function requires the caller to have the necessary permissions to access the file in Google Workspace.

    Args:
        name (str): The name of the file to get.
        folder_id (str, optional): The id of the folder to search in. If None, search in all folders.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        list: A list of files that match the name within the folder.
    """
    q = f"trashed=false and name='{name}'"
    if folder_id:
        q += f" and '{folder_id}' in parents"
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    files = service.files()
    # Shared drives are part of this workspace's Drive layout.
    request = files.list(
        q=q,
        fields=fields,
        pageSize=pageSize,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
    )
    return _collect_files(files, request)


def list_folders_in_folder(
    folder: str,
    query: str | None = None,
    *,
    fields: str | None = None,
    pageSize: int = 100,
    delegated_user_email: str | None = None,
) -> list[dict[str, Any]]:
    """List all folders in a folder in Google Drive.

    Args:
        folder (str): The id of the folder to list.
        query (str, optional): A query to filter the folders.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        list: A list of folders in the folder.
    """
    base_query = f"parents in '{folder}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false"
    if query:
        base_query += f" and {query}"

    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    files = service.files()
    # Shared drives are part of this workspace's Drive layout.
    request = files.list(
        q=base_query,
        fields=fields,
        pageSize=pageSize,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
    )
    return _collect_files(files, request)


def list_files_in_folder(
    folder: str,
    *,
    fields: str | None = None,
    pageSize: int = 100,
    delegated_user_email: str | None = None,
) -> list[dict[str, Any]]:
    """List all files in a folder in Google Drive.

    Args:
        folder (str): The id of the folder to list.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        list: A list of files in the folder.
    """
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    files = service.files()
    # Shared drives are part of this workspace's Drive layout.
    request = files.list(
        q=f"parents in '{folder}' and mimeType != 'application/vnd.google-apps.folder' and trashed=false",
        fields=fields,
        pageSize=pageSize,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
    )
    return _collect_files(files, request)


def copy_file_to_folder(
    file_id: str,
    name: str,
    parent_folder_id: str,
    destination_folder_id: str,
    *,
    delegated_user_email: str | None = None,
) -> str:
    """Copy a file to a new folder in Google Drive.

    Args:
        file_id (str): The id of the file to copy.
        name (str): The name of the new file.
        parent_folder_id (str): The id of the parent folder.
        destination_folder_id (str): The id of the destination folder.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        str: The id of the new file.
    """
    service = google_service_client.get_drive_service(scopes=DRIVE_SCOPES, delegated_user_email=delegated_user_email)
    files = service.files()
    copied_file = cast(
        str,
        _execute_file_request(
            files.copy(
                fileId=file_id,
                body=cast("File", {"name": name, "parents": [parent_folder_id]}),
                supportsAllDrives=True,
                fields="id",
            )
        )["id"],
    )
    logger.debug("google_drive_file_copied", file_id=copied_file)
    updated_file = cast(
        str,
        _execute_file_request(
            files.update(
                fileId=copied_file,
                body=cast("File", {}),
                addParents=destination_folder_id,
                removeParents=parent_folder_id,
                supportsAllDrives=True,
                fields="id",
            )
        )["id"],
    )
    logger.debug("google_drive_file_moved", file_id=updated_file)
    return updated_file


def healthcheck() -> bool:
    """Check the health of the Google Drive API.

    Returns:
        bool: True if the API is healthy, False otherwise.
    """
    healthy = False
    try:
        metadata = list_metadata(INCIDENT_TEMPLATE)
        if metadata is not None:
            healthy = "id" in metadata
        logger.info(
            "google_drive_healthcheck_success",
            status="healthy" if healthy else "unhealthy",
        )
    except Exception as error:
        logger.exception("google_drive_healthcheck_failed", error=str(error))

    return healthy
