import os
import pickle
import base64
import logging
import datetime

from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()

SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
INCIDENT_TEMPLATE = os.environ.get("INCIDENT_TEMPLATE")
INCIDENT_LIST = os.environ.get("INCIDENT_LIST")
START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"

PICKLE_STRING = os.environ.get("PICKLE_STRING", False)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/docs",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]


def get_google_service(service, version):
    creds = None

    if PICKLE_STRING is False:
        raise Exception("Pickle string not set")

    try:
        pickle_string = base64.b64decode(PICKLE_STRING)
        # ignore Bandit complaint about insecure pickle
        creds = pickle.loads(pickle_string)  # nosec
    except Exception as pickle_read_exception:
        logging.error(
            "Error while loading pickle string: {}".format(pickle_read_exception)
        )
        raise Exception("Invalid pickle string")

    return build(service, version, credentials=creds)


def create_new_folder(name, parent_folder):
    # Creates a new folder in the parent_folder directory
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
    return results["id"]


def create_new_incident(name, folder):
    service = get_google_service("drive", "v3")
    result = (
        service.files()
        .copy(
            fileId=INCIDENT_TEMPLATE,
            body={"name": name, "parents": [folder]},
            supportsAllDrives=True,
        )
        .execute()
    )
    return result["id"]


def copy_file_to_folder(file_id, name, parent_folder_id, destination_folder_id):
    # Copies a file from the parent_folder to the destination_folder
    # create the copy
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


def create_new_docs_file(name, parent_folder_id):
    # Creates a new google docs file in the parent_folder directory
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.document",
                "parents": [parent_folder_id],
            },
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
    )
    return results["id"]


def create_new_sheets_file(name, parent_folder_id):
    # Creates a new google sheets file in the parent_folder directory
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [parent_folder_id],
            },
            supportsAllDrives=True,
            fields="id",
        )
        .execute()
    )
    return results["id"]


def list_folders():
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .list(
            pageSize=25,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive",
            q="parents in '{}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false and not name contains '{}'".format(
                SRE_INCIDENT_FOLDER, "Templates"
            ),
            driveId=SRE_DRIVE_ID,
            fields="nextPageToken, files(id, name)",
        )
        .execute()
    )
    return results.get("files", [])


def list_metadata(file_id):
    service = get_google_service("drive", "v3")
    result = (
        service.files()
        .get(supportsAllDrives=True, fileId=file_id, fields="id, name, appProperties")
        .execute()
    )
    return result


def merge_data(file_id, name, product, slack_channel, on_call_names):
    changes = {
        "requests": [
            {
                "replaceAllText": {
                    "containsText": {"text": "{{date}}", "matchCase": "true"},
                    "replaceText": datetime.datetime.now().strftime("%Y-%m-%d"),
                }
            },
            {
                "replaceAllText": {
                    "containsText": {"text": "{{name}}", "matchCase": "true"},
                    "replaceText": str(name),
                }
            },
            {
                "replaceAllText": {
                    "containsText": {"text": "{{on-call-names}}", "matchCase": "true"},
                    "replaceText": str(on_call_names),
                }
            },
            {
                "replaceAllText": {
                    "containsText": {"text": "{{team}}", "matchCase": "true"},
                    "replaceText": str(product),
                }
            },
            {
                "replaceAllText": {
                    "containsText": {"text": "{{slack-channel}}", "matchCase": "true"},
                    "replaceText": str(slack_channel),
                }
            },
            {
                "replaceAllText": {
                    "containsText": {"text": "{{status}}", "matchCase": "true"},
                    "replaceText": "In Progress",
                }
            },
        ]
    }
    service = get_google_service("docs", "v1")
    result = (
        service.documents()
        .batchUpdate(
            documentId=file_id,
            body=changes,
        )
        .execute()
    )
    return result


def update_incident_list(document_link, name, slug, product, channel_url):
    service = get_google_service("sheets", "v4")
    list = [
        [
            datetime.datetime.now().strftime("%Y-%m-%d"),
            f'=HYPERLINK("{document_link}", "{name}")',
            product,
            "In Progress",
            f'=HYPERLINK("{channel_url}", "#{slug}")',
        ]
    ]
    resource = {"majorDimension": "ROWS", "values": list}
    range = "Sheet1!A:A"
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=INCIDENT_LIST,
            range=range,
            body=resource,
            valueInputOption="USER_ENTERED",
        )
        .execute()
    )

    return result


def healthcheck():
    """Check if the bot can interact with Google Drive."""
    healthy = False
    try:
        metadata = list_metadata(INCIDENT_TEMPLATE)
        healthy = "id" in metadata
        logging.info(f"Google Drive healthcheck result: {metadata}")
    except Exception as error:
        logging.error(f"Google Drive healthcheck failed: {error}")
    return healthy
