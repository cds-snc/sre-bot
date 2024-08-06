"""
Google Drive Module.

This module provides functionalities to interact with Google Drive. It includes functions to add metadata to a file, create a new folder, create a new document from a template, and copy a file to a new folder.
"""

import os
from integrations.google_workspace.google_service import (
    handle_google_api_errors,
    execute_google_api_call,
)

INCIDENT_TEMPLATE = os.environ.get("INCIDENT_TEMPLATE")


@handle_google_api_errors
def add_metadata(file_id, key, value):
    """Add metadata to a file in Google Drive.

    Args:
        file_id (str): The file id of the file to add metadata to.
        key (str): The key of the metadata to add.
        value (str): The value of the metadata to add.

    Returns:
        dict: The updated file metadata.
    """
    return execute_google_api_call(
        "drive",
        "v3",
        "files",
        "update",
        fileId=file_id,
        body={"appProperties": {key: value}},
        fields="name, appProperties",
        supportsAllDrives=True,
    )


@handle_google_api_errors
def delete_metadata(file_id, key):
    """Delete metadata from a file in Google Drive.

    Args:
        file_id (str): The file id of the file to delete metadata from.
        key (str): The key of the metadata to delete.

    Returns:
        dict: The updated file metadata.
    """
    return execute_google_api_call(
        "drive",
        "v3",
        "files",
        "update",
        fileId=file_id,
        body={"appProperties": {key: None}},
        fields="name, appProperties",
        supportsAllDrives=True,
    )


@handle_google_api_errors
def list_metadata(file_id):
    """List metadata of a file in Google Drive.

    Args:
        file_id (str): The file id of the file to list metadata from.

    Returns:
        dict: The file metadata.
    """
    return execute_google_api_call(
        "drive",
        "v3",
        "files",
        "get",
        fileId=file_id,
        fields="id, name, appProperties",
        supportsAllDrives=True,
    )


@handle_google_api_errors
def create_folder(name, parent_folder):
    """Create a new folder in Google Drive.

    Args:
        name (str): The name of the new folder.
        parent_folder (str): The id of the parent folder.

    Returns:
        str: The id of the new folder.
    """
    result = execute_google_api_call(
        "drive",
        "v3",
        "files",
        "create",
        body={
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder],
        },
        supportsAllDrives=True,
        fields="id",
    )

    return result


@handle_google_api_errors
def create_file_from_template(name, folder, template):
    """Create a new file in Google Drive from a template
     (Docs, Sheets, Slides, Forms, or Sites.)

    Args:
        name (str): The name of the new file.
        folder (str): The id of the folder to create the file in.
        template (str): The id of the template to use.

    Returns:
        str: The id of the new file.
    """
    result = execute_google_api_call(
        "drive",
        "v3",
        "files",
        "copy",
        fileId=template,
        body={"name": name, "parents": [folder]},
        supportsAllDrives=True,
        fields="id",
    )

    return result["id"]


@handle_google_api_errors
def create_file(name, folder, file_type):
    """Create a new file in Google Drive.
        Options for 'file_type' are:

            - "document": Google Docs
            - "spreadsheet": Google Sheets
            - "presentation": Google Slides
            - "form": Google Forms
            - "site": Google Sites

    Args:
        name (str): The name of the new file.
        folder (str): The id of the folder to create the file in.
        file_type (str): The type of the new file.

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

    result = execute_google_api_call(
        "drive",
        "v3",
        "files",
        "create",
        body={"name": name, "parents": [folder], "mimeType": mime_type_value},
        supportsAllDrives=True,
        fields="id",
    )

    return result["id"]


@handle_google_api_errors
def get_file_by_name(name, folder_id=None):
    """Get a file by name in a specific Google Drive folder.

    This function requires the caller to have the necessary permissions to access the file in Google Workspace.

    Args:
        name (str): The name of the file to get.
        folder_id (str, optional): The id of the folder to search in. If None, search in all folders.

    Returns:
        list: A list of files that match the name within the folder.
    """
    q = f"trashed=false and name='{name}'"
    if folder_id:
        q += f" and '{folder_id}' in parents"
    return execute_google_api_call(
        "drive",
        "v3",
        "files",
        "list",
        scopes=["https://www.googleapis.com/auth/drive.readonly"],
        paginate=True,
        pageSize=1,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q=q,
        fields="files(appProperties, id, name)",
    )


@handle_google_api_errors
def list_folders_in_folder(folder, query=None):
    """List all folders in a folder in Google Drive.

    Args:
        folder (str): The id of the folder to list.
        query (str, optional): A query to filter the folders.

    Returns:
        list: A list of folders in the folder.
    """
    base_query = f"parents in '{folder}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false"
    if query:
        base_query += f" and {query}"

    return execute_google_api_call(
        "drive",
        "v3",
        "files",
        "list",
        paginate=True,
        pageSize=25,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q=base_query,
        fields="files(id, name)",
    )


@handle_google_api_errors
def list_files_in_folder(folder):
    """List all files in a folder in Google Drive.

    Args:
        folder (str): The id of the folder to list.

    Returns:
        list: A list of files in the folder.
    """
    return execute_google_api_call(
        "drive",
        "v3",
        "files",
        "list",
        paginate=True,
        pageSize=25,
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        corpora="user",
        q=f"parents in '{folder}' and mimeType != 'application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    )


@handle_google_api_errors
def copy_file_to_folder(file_id, name, parent_folder_id, destination_folder_id):
    """Copy a file to a new folder in Google Drive.

    Args:
        file_id (str): The id of the file to copy.
        name (str): The name of the new file.
        parent_folder_id (str): The id of the parent folder.
        destination_folder_id (str): The id of the destination folder.

    Returns:
        str: The id of the new file.
    """
    copied_file = execute_google_api_call(
        "drive",
        "v3",
        "files",
        "copy",
        fileId=file_id,
        body={"name": name, "parents": [parent_folder_id]},
        supportsAllDrives=True,
        fields="id",
    )

    # move the copy to the new folder
    updated_file = execute_google_api_call(
        "drive",
        "v3",
        "files",
        "update",
        fileId=copied_file["id"],
        addParents=destination_folder_id,
        removeParents=parent_folder_id,
        supportsAllDrives=True,
        fields="id",
    )

    return updated_file["id"]


@handle_google_api_errors
def healthcheck():
    """Check the health of the Google Drive API.

    Returns:
        bool: True if the API is healthy, False otherwise.
    """
    healthy = False
    metadata = list_metadata(INCIDENT_TEMPLATE)
    if metadata is not None:
        healthy = "id" in metadata

    return healthy
