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
START_HEADING = "Detailed Timeline"
END_HEADING = "Trigger"

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


def add_metadata(file_id, key, value):
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
    return result


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


def delete_metadata(file_id, key):
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


def get_document_by_channel_name(channel_name):
    service = get_google_service("drive", "v3")
    results = (
        service.files()
        .list(
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive",
            q="trashed=false and name='{}'".format(channel_name),
            driveId=SRE_DRIVE_ID,
            fields="files(appProperties, id, name)",
        )
        .execute()
    )
    return results.get("files", [])


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


def get_timeline_section(document_id):
    # Retrieve the document
    service = get_google_service("docs", "v1")
    document = service.documents().get(documentId=document_id).execute()
    content = document.get("body").get("content")

    timeline_content = ""
    record = False

    # Iterate through the elements of the document in order to return the content between the headings (START_HEADING and END_HEADING)
    for element in content:
        if "paragraph" in element:
            paragraph_elements = element.get("paragraph").get("elements")
            for elem in paragraph_elements:
                text_run = elem.get("textRun")
                if text_run:
                    text = text_run.get("content")
                    if END_HEADING in text:
                        record = False
                        break
                    if START_HEADING in text:
                        record = True
                        continue
                    if record:
                        timeline_content += text

    return timeline_content


# Replace the text between the headings
def replace_text_between_headings(doc_id, new_content, start_heading, end_heading):
    # Setup the service
    service = get_google_service("docs", "v1")

    # Retrieve the document content
    document = service.documents().get(documentId=doc_id).execute()
    content = document.get("body").get("content")

    # Find the start and end indices
    start_index = None
    end_index = None
    for element in content:
        if "paragraph" in element:
            paragraph = element.get("paragraph")
            text_runs = paragraph.get("elements")
            for text_run in text_runs:
                text = text_run.get("textRun").get("content")
                if start_heading in text:
                    # Set start_index to the end of the start heading
                    start_index = text_run.get("endIndex")
                if end_heading in text and start_index is not None:
                    # Set end_index to the start of the end heading
                    end_index = text_run.get("startIndex")
                    break

    if start_index is not None and end_index is not None:
        # Format new content with new lines for proper insertion
        formatted_content = "\n" + new_content + "\n"
        content_length = len(formatted_content)

        # Perform the replacement
        requests = [
            {
                "deleteContentRange": {
                    "range": {"startIndex": start_index, "endIndex": end_index}
                }
            },
            {
                "insertText": {
                    "location": {"index": start_index},
                    "text": formatted_content,
                }
            },
        ]
        # Format the inserted text - we want to make sure that the font size is what we want
        requests.append(
            {
                "updateTextStyle": {
                    "range": {
                        "startIndex": start_index,
                        "endIndex": (
                            start_index + content_length
                        ),  # Adjust this index based on the length of the text
                    },
                    "textStyle": {
                        "fontSize": {"magnitude": 11, "unit": "PT"},
                        "bold": False,
                    },
                    "fields": "bold",
                }
            }
        )
        # Update paragraph style to be normal text
        requests.append(
            {
                "updateParagraphStyle": {
                    "range": {
                        "startIndex": start_index + 1,
                        "endIndex": (
                            start_index + content_length
                        ),  # Adjust this index based on the length of the text
                    },
                    "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                    "fields": "namedStyleType",
                }
            }
        )
        service.documents().batchUpdate(
            documentId=doc_id, body={"requests": requests}
        ).execute()
    else:
        logging.warning("Headings not found")


# Update the incident document with status of "Closed"
def close_incident_document(file_id):
    # List of possible statuses to be replaced
    possible_statuses = ["In Progress", "Open", "Ready to be Reviewed", "Reviewed"]

    # Replace all possible statuses with "Closed"
    changes = {
        "requests": [
            {
                "replaceAllText": {
                    "containsText": {"text": f"Status: {status}", "matchCase": "false"},
                    "replaceText": "Status: Closed",
                }
            }
            for status in possible_statuses
        ]
    }
    # Execute the batchUpdate request
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


def update_spreadsheet_close_incident(channel_name):
    # Find the row in the spreadsheet with the channel_name and update it's status to Closed
    # Read the data from the sheet
    service = get_google_service("sheets", "v4")
    sheet_name = "Sheet1"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=INCIDENT_LIST, range=sheet_name)
        .execute()
    )
    values = result.get("values", [])
    # Find the row with the search value
    for i, row in enumerate(values):
        if channel_name in row:
            # Update the 4th column (index 3) of the found row
            update_range = (
                f"{sheet_name}!D{i+1}"  # Column D, Rows are 1-indexed in Sheets
            )
            body = {"values": [["Closed"]]}
            service.spreadsheets().values().update(
                spreadsheetId=INCIDENT_LIST,
                range=update_range,
                valueInputOption="USER_ENTERED",
                body=body,
            ).execute()
            return True
    return False
