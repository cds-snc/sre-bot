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

PICKLE_STRING = os.environ.get("PICKLE_STRING", False)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/docs",
    "https://www.googleapis.com/auth/spreadsheets",
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


def create_folder(name):
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .create(
            body={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [SRE_INCIDENT_FOLDER],
            },
            supportsAllDrives=True,
            fields="name",
        )
        .execute()
    )
    return f"Created folder {results['name']}"


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


def merge_data(file_id, name, product, slack_channel):
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
