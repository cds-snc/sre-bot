"""
Google Drive Module.

This module provides functionalities to interact with Google Drive. It includes functions to add metadata to a file, create a new folder, create a new document from a template, and copy a file to a new folder.
"""

import structlog
from integrations.google_workspace import google_service

INCIDENT_TEMPLATE = google_service.INCIDENT_TEMPLATE
DELEGATED_USER_EMAIL = google_service.SRE_BOT_EMAIL

logger = structlog.get_logger()
handle_google_api_errors = google_service.handle_google_api_errors


@handle_google_api_errors
def add_metadata(file_id: str, key: str, value: str, **kwargs):
    """Add metadata to a file in Google Drive.

    Args:
        file_id (str): The file id of the file to add metadata to.
        key (str): The key of the metadata to add.
        value (str): The value of the metadata to add.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The updated file metadata.
    """
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "update",
        scopes=["https://www.googleapis.com/auth/drive"],
        fileId=file_id,
        body={"appProperties": {key: value}},
        fields="name, appProperties",
        supportsAllDrives=True,
        **kwargs,
    )


@handle_google_api_errors
def delete_metadata(file_id, key, **kwargs):
    """Delete metadata from a file in Google Drive.

    Args:
        file_id (str): The file id of the file to delete metadata from.
        key (str): The key of the metadata to delete.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The updated file metadata.
    """
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "update",
        scopes=["https://www.googleapis.com/auth/drive"],
        fileId=file_id,
        body={"appProperties": {key: None}},
        fields="name, appProperties",
        supportsAllDrives=True,
        **kwargs,
    )


@handle_google_api_errors
def list_metadata(file_id: str, **kwargs) -> dict:
    """List metadata of a file in Google Drive.

    Args:
        file_id (str): The file id of the file to list metadata from.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The file metadata.
    """
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "get",
        scopes=["https://www.googleapis.com/auth/drive"],
        fileId=file_id,
        fields="id, name, appProperties",
        supportsAllDrives=True,
        **kwargs,
    )


@handle_google_api_errors
def create_folder(
    name: str,
    parent_folder: str,
    fields: str | None = None,
    **kwargs,
) -> dict:
    """Create a new folder in Google Drive.

    Args:
        name (str): The name of the new folder.
        parent_folder (str): The id of the parent folder.
        fields (str, optional): The fields to include in the response.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: A File resource representing the new folder.
        (https://developers.google.com/drive/api/reference/rest/v3/files#File)
    """
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "create",
        scopes=["https://www.googleapis.com/auth/drive"],
        body={
            "name": name,
            "parents": [parent_folder],
            "mimeType": "application/vnd.google-apps.folder",
        },
        supportsAllDrives=True,
        fields=fields,
        **kwargs,
    )


@handle_google_api_errors
def create_file_from_template(
    name: str,
    folder: str,
    template: str,
    fields: str | None = None,
    **kwargs,
) -> dict:
    """Create a new file in Google Drive from a template (Docs, Sheets, Slides, Forms, or Sites.)

    Args:
        name (str): The name of the new file.
        folder (str): The id of the folder to create the file in.
        template (str): The id of the template to use.
        fields (str, optional): The fields to include in the response.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: A File resource representing the new file with a mask of 'id'.
    """
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "copy",
        scopes=["https://www.googleapis.com/auth/drive"],
        fileId=template,
        body={"name": name, "parents": [folder]},
        supportsAllDrives=True,
        fields=fields,
        **kwargs,
    )


@handle_google_api_errors
def create_file(name, folder, file_type, **kwargs):
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

    mime_type_value = mime_type[file_type]

    result = google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "create",
        scopes=["https://www.googleapis.com/auth/drive"],
        body={"name": name, "parents": [folder], "mimeType": mime_type_value},
        supportsAllDrives=True,
        fields="id, name",
        **kwargs,
    )

    return result


@handle_google_api_errors
def get_file_by_id(file_id: str, **kwargs) -> dict:
    """Get a file by id in Google Drive.

    Args:
        fileId (str): The id of the file to get.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        dict: The file metadata.
    """
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "get",
        scopes=["https://www.googleapis.com/auth/drive"],
        fileId=file_id,
        supportsAllDrives=True,
        **kwargs,
    )


@handle_google_api_errors
def find_files_by_name(name, folder_id=None, **kwargs):
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
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["https://www.googleapis.com/auth/drive"],
        paginate=True,
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q=q,
        fields="files(appProperties, id, name)",
        **kwargs,
    )


@handle_google_api_errors
def list_folders_in_folder(folder, query=None, **kwargs):
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

    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["https://www.googleapis.com/auth/drive"],
        paginate=True,
        pageSize=25,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q=base_query,
        fields="files(id, name)",
        **kwargs,
    )


@handle_google_api_errors
def list_files_in_folder(
    folder: str,
    **kwargs,
):
    """List all files in a folder in Google Drive.

    Args:
        folder (str): The id of the folder to list.
        **kwargs: Additional keyword arguments to pass to the API call. e.g., `delegated_user_email`.

    Returns:
        list: A list of files in the folder.
    """
    return google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["https://www.googleapis.com/auth/drive"],
        paginate=True,
        pageSize=25,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q=f"parents in '{folder}' and mimeType != 'application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
        **kwargs,
    )


@handle_google_api_errors
def copy_file_to_folder(
    file_id: str,
    name: str,
    parent_folder_id: str,
    destination_folder_id: str,
    **kwargs,
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
    copied_file = google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "copy",
        scopes=["https://www.googleapis.com/auth/drive"],
        fileId=file_id,
        body={"name": name, "parents": [parent_folder_id]},
        supportsAllDrives=True,
        fields="id",
        **kwargs,
    )[0]["id"]
    print(f"Copied file: {copied_file}")

    # move the copy to the new folder
    updated_file = google_service.execute_google_api_call(
        "drive",
        "v3",
        "files",
        "update",
        scopes=["https://www.googleapis.com/auth/drive"],
        fileId=copied_file,
        addParents=destination_folder_id,
        removeParents=parent_folder_id,
        supportsAllDrives=True,
        fields="id",
        **kwargs,
    )[0]["id"]
    print(f"Updated file: {updated_file}")

    return updated_file


@handle_google_api_errors
def healthcheck():
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
