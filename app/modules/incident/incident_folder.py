"""Module for managing SRE incident folders in Google Drive.

Includes functions to manage the folders, the metadata, and the list of incidents in a Google Sheets spreadsheet.
"""

import datetime
import os
from slack_sdk.web import WebClient
from slack_bolt import Ack
from integrations.google_workspace import google_drive, sheets
import logging

SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
INCIDENT_LIST = os.environ.get("INCIDENT_LIST")


def list_incident_folders():
    folders = google_drive.list_folders_in_folder(
        SRE_INCIDENT_FOLDER, "not name contains 'Templates'"
    )
    folders.sort(key=lambda x: x["name"])
    return folders


def list_folders_view(client: WebClient, body, ack: Ack):
    ack()
    folders = google_drive.list_folders_in_folder(
        SRE_INCIDENT_FOLDER, "not name contains 'Templates'"
    )
    folders.sort(key=lambda x: x["name"])
    blocks = {
        "type": "modal",
        "callback_id": "list_folders_view",
        "title": {"type": "plain_text", "text": "SRE - Listing folders"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            item for sublist in list(map(folder_item, folders)) for item in sublist
        ],
    }
    client.views_open(trigger_id=body["trigger_id"], view=blocks)


def delete_folder_metadata(client: WebClient, body, ack):
    ack()
    folder_id = body["view"]["private_metadata"]
    key = body["actions"][0]["value"]
    response = google_drive.delete_metadata(folder_id, key)
    if not response:
        logging.info(f"Failed to delete metadata `{key}` for folder `{folder_id}`")
    else:
        logging.info(f"Deleted metadata for key `{key}`")
    body["actions"] = [{"value": folder_id}]
    view_folder_metadata(client, body, ack)


def save_metadata(client: WebClient, body, ack, view):
    ack()
    folder_id = view["private_metadata"]
    key = view["state"]["values"]["key"]["key"]["value"]
    value = view["state"]["values"]["value"]["value"]["value"]
    google_drive.add_metadata(folder_id, key, value)
    body["actions"] = [{"value": folder_id}]
    del body["view"]
    view_folder_metadata(client, body, ack)


def get_folder_metadata(folder_id):
    return google_drive.list_metadata(folder_id)


def view_folder_metadata(client, body, ack):
    ack()
    folder_id = body["actions"][0]["value"]
    logging.info(f"Viewing metadata for folder {folder_id}")
    folder = google_drive.list_metadata(folder_id)
    blocks = {
        "type": "modal",
        "callback_id": "view_folder_metadata_modal",
        "title": {"type": "plain_text", "text": "SRE - Showing metadata"},
        "submit": {"type": "plain_text", "text": "Return to folders"},
        "private_metadata": folder_id,
        "blocks": (
            [
                {
                    "type": "section",
                    "text": {
                        "type": "plain_text",
                        "text": folder["name"],
                    },
                    "accessory": {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Add metadata"},
                        "value": folder_id,
                        "action_id": "add_folder_metadata",
                    },
                },
                {"type": "divider"},
            ]
            + metadata_items(folder)
        ),
    }
    if "view" in body:
        client.views_update(
            view_id=body["view"]["id"],
            view=blocks,
        )
    else:
        client.views_open(trigger_id=body["trigger_id"], view=blocks)


def add_folder_metadata(client: WebClient, body, ack):
    ack()
    folder_id = body["actions"][0]["value"]
    blocks = {
        "type": "modal",
        "callback_id": "add_metadata_view",
        "title": {"type": "plain_text", "text": "SRE - Add metadata"},
        "submit": {"type": "plain_text", "text": "Save metadata"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "private_metadata": folder_id,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Add metadata*",
                },
            },
            {
                "type": "input",
                "block_id": "key",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "key",
                    "placeholder": {"type": "plain_text", "text": "Key"},
                },
                "label": {
                    "type": "plain_text",
                    "text": "Key",
                },
            },
            {
                "type": "input",
                "block_id": "value",
                "element": {
                    "type": "plain_text_input",
                    "action_id": "value",
                    "placeholder": {"type": "plain_text", "text": "Value"},
                },
                "label": {
                    "type": "plain_text",
                    "text": "Value",
                },
            },
        ],
    }
    client.views_update(
        view_id=body["view"]["id"],
        view=blocks,
    )


def folder_item(folder):
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{folder['name']}*"},
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Manage metadata",
                    "emoji": True,
                },
                "value": f"{folder['id']}",
                "action_id": "view_folder_metadata",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"<https://drive.google.com/drive/u/0/folders/{folder['id']}|View in Google Drive>",
                }
            ],
        },
        {"type": "divider"},
    ]


def metadata_items(folder):
    if "appProperties" not in folder or len(folder["appProperties"]) == 0:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*No metadata found. Click the button above to add metadata.*",
                },
            },
        ]
    else:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{key}*\n{value}",
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Delete metadata",
                        "emoji": True,
                    },
                    "value": key,
                    "style": "danger",
                    "action_id": "delete_folder_metadata",
                },
            }
            for key, value in folder["appProperties"].items()
        ]


def add_new_incident_to_list(document_link, name, slug, product, channel_url):
    """Update the incident list spreadsheet with a new incident.

    Args:
        document_link (str): The link to the incident document.
        name (str): The name of the incident.
        slug (str): The slug of the incident.
        product (str): The product affected by the incident.
        channel_url (str): The link to the Slack channel for the incident.

    Returns:
        bool: True if the incident was added successfully, False otherwise.
    """
    list = [
        [
            datetime.datetime.now().strftime("%Y-%m-%d"),
            f'=HYPERLINK("{document_link}", "{name}")',
            product,
            "In Progress",
            f'=HYPERLINK("{channel_url}", "#{slug}")',
        ]
    ]
    range = "Sheet1!A:A"
    body = {
        "majorDimension": "ROWS",
        "values": list,
    }
    updated_sheet = sheets.append_values(INCIDENT_LIST, range, body)
    return updated_sheet


def update_spreadsheet_incident_status(channel_name, status="Closed"):
    """Update the status of an incident in the incident list spreadsheet.

    Args:
        channel_name (str): The name of the channel to update.
        status (str): The status to update the incident to.

    Returns:
        bool: True if the status was updated successfully, False otherwise.
    """
    valid_statuses = ["Open", "Closed", "In Progress", "Resolved"]
    if status not in valid_statuses:
        logging.warning("Invalid status %s", status)
        return False
    sheet_name = "Sheet1"
    sheet = sheets.get_values(INCIDENT_LIST, range=sheet_name)
    values = sheet.get("values", [])
    if len(values) == 0:
        logging.warning("No incident found for channel %s", channel_name)
        return False
    # Find the row with the search value
    for i, row in enumerate(values):
        if channel_name in row:
            # Update the 4th column (index 3) of the found row
            update_range = (
                f"{sheet_name}!D{i+1}"  # Column D, Rows are 1-indexed in Sheets
            )
            updated_sheet = sheets.batch_update_values(
                INCIDENT_LIST, update_range, [[status]]
            )
            if updated_sheet:
                return True
    return False
