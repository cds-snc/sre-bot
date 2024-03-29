"""
Google Drive Module.

This module provides functionalities to interact with Google Drive. It includes functions to add metadata to a file, create a new folder, create a new document from a template, and copy a file to a new folder.

Functions:
    add_metadata(file_id: str, key: str, value: str) -> dict:
        Adds metadata to a file in Google Drive and returns the updated file metadata.

    delete_metadata(file_id: str, key: str) -> dict:
        Deletes metadata from a file in Google Drive and returns the updated file metadata.

    list_metadata(file_id: str) -> dict:
        Lists metadata of a file in Google Drive and returns the file metadata.

    create_folder(name: str, parent_folder: str) -> str:
        Creates a new folder in Google Drive and returns the id of the new folder.

    create_file_from_template(name: str, folder: str, template: str) -> str:
        Creates a new document in Google Drive from a template (Docs, Sheets, Slides, Forms, or Sites) and returns the id of the new document.

    create_file(name: str, folder: str, file_type: str) -> str:
        Creates a new file in Google Drive and returns the id of the new file.

    get_file_by_name(name: str, folder: str) -> list:
        Gets a file by name in Google Drive and returns a list of files that match the name.

    list_folders_in_folder(folder: str) -> list:
        Lists all folders in a folder in Google Drive and returns a list of folders in the folder.

    copy_file_to_folder(file_id: str, name: str, parent_folder_id: str, destination_folder_id: str) -> str:
        Copies a file to a new folder in Google Drive and returns the id of the new file.

    healthcheck() -> bool:
        Checks the health of the Google Drive API and returns True if the API is healthy, False otherwise.
"""
import os
from integrations.google_workspace.google_service import (
    get_google_service,
    handle_google_api_errors,
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
    # pylint: disable=no-member
    service = get_google_service("drive", "v3")
    result = (
        service.files()
        .update(
            fileId=file_id,
            body={"appProperties": {key: value}},
            fields="name, appProperties",
            supportsAllDrives=True,
        )
        .execute()
    )
    # pylint: enable=no-member

    return result


@handle_google_api_errors
def delete_metadata(file_id, key):
    """Delete metadata from a file in Google Drive.

    Args:
        file_id (str): The file id of the file to delete metadata from.
        key (str): The key of the metadata to delete.

    Returns:
        dict: The updated file metadata.
    """
    service = get_google_service("drive", "v3")
    result = (
        service.files()
        .update(
            fileId=file_id,
            body={"appProperties": {key: None}},
            fields="name, appProperties",
            supportsAllDrives=True,
        )
        .execute()
    )
    return result


@handle_google_api_errors
def list_metadata(file_id):
    """List metadata of a file in Google Drive.

    Args:
        file_id (str): The file id of the file to list metadata from.

    Returns:
        dict: The file metadata.
    """
    service = get_google_service("drive", "v3")
    result = (
        service.files()
        .get(fileId=file_id, fields="id, name, appProperties", supportsAllDrives=True)
        .execute()
    )
    return result


@handle_google_api_errors
def create_folder(name, parent_folder):
    """Create a new folder in Google Drive.

    Args:
        name (str): The name of the new folder.
        parent_folder (str): The id of the parent folder.

    Returns:
        str: The id of the new folder.
    """
    # pylint: disable=no-member
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_folder],
            },
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
    )
    # pylint: enable=no-member

    return results["id"]


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
    # pylint: disable=no-member
    service = get_google_service("drive", "v3")
    result = (
        service.files()
        .copy(
            fileId=template,
            body={"name": name, "parents": [folder]},
            supportsAllDrives=True,
        )
        .execute()
    )
    # pylint: enable=no-member
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

    service = get_google_service("drive", "v3")
    result = (
        service.files()
        .create(
            body={"name": name, "parents": [folder], "mimeType": mime_type_value},
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
    )
    return result["id"]


@handle_google_api_errors
def get_file_by_name(name, folder):
    """Get a file by name in Google Drive.

    Args:
        name (str): The name of the file to get.
        folder (str): The id of the folder to search in.

    Returns:
        list: A list of files that match the name.
    """
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .list(
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive",
            q="trashed=false and name='{}'".format(name),
            driveId=folder,
            fields="files(appProperties, id, name)",
        )
        .execute()
    )
    return results.get("files", [])


@handle_google_api_errors
def list_folders_in_folder(folder):
    """List all folders in a folder in Google Drive.

    Args:
        folder (str): The id of the folder to list.

    Returns:
        list: A list of folders in the folder.
    """
    service = get_google_service("drive", "v3")
    page_token = None
    all_files = []
    while True:
        results = (
            service.files()
            .list(
                pageSize=25,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="user",
                q="parents in '{}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false".format(
                    folder
                ),
                fields="nextPageToken, files(id, name)",
                pageToken=page_token,
            )
            .execute()
        )
        all_files.extend(results.get("files", []))
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    return all_files


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
    service = get_google_service("drive", "v3")
    copied_file = (
        service.files()
        .copy(
            fileId=file_id,
            body={"name": name, "parents": [parent_folder_id]},
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
    )
    # move the copy to the new folder
    updated_file = (
        service.files()
        .update(
            fileId=copied_file["id"],
            addParents=destination_folder_id,
            removeParents=parent_folder_id,
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
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
