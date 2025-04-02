"""Module for managing SRE incident folders in Google Drive.

Includes functions to manage the folders, the metadata, and the list of incidents in a Google Sheets spreadsheet.
"""

import datetime
import pytz

import re
import time
from slack_sdk.web import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import Ack
from integrations.google_workspace import google_drive, sheets
from integrations.aws import dynamodb
from modules.incident import db_operations
from core.config import settings
from core.logging import get_module_logger

SRE_INCIDENT_FOLDER = settings.feat_incident.SRE_INCIDENT_FOLDER
INCIDENT_LIST = settings.feat_incident.INCIDENT_LIST

logger = get_module_logger()


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
        logger.warning(
            "metadata_delete_failed",
            key=key,
            folder_id=folder_id,
        )
    else:
        logger.info(
            "metadata_delete_success",
            key=key,
            folder_id=folder_id,
        )
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


def get_folder_metadata(folder_id) -> dict:
    """Get metadata for a folder."""
    return google_drive.list_metadata(folder_id)


def view_folder_metadata(client, body, ack):
    ack()
    folder_id = body["actions"][0]["value"]
    logger.info(
        "view_folder_metadata",
        folder_id=folder_id,
    )
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
    incident_data = [
        [
            datetime.datetime.now().strftime("%Y-%m-%d"),
            f'=HYPERLINK("{document_link}", "{name}")',
            product,
            "In Progress",
            f'=HYPERLINK("{channel_url}", "#{slug}")',
        ]
    ]
    cell_range = "Sheet1!A:A"
    body = {
        "majorDimension": "ROWS",
        "values": incident_data,
    }
    updated_sheet = sheets.append_values(INCIDENT_LIST, cell_range, body)
    return updated_sheet


def update_spreadsheet_incident_status(channel_name, status="Closed"):
    """Update the status of an incident in the incident list spreadsheet.

    Args:
        channel_name (str): The name of the channel to update.
        status (str): The status to update the incident to.

    Returns:
        bool: True if the status was updated successfully, False otherwise.
    """
    valid_statuses = [
        "In Progress",
        "Open",
        "Ready to be Reviewed",
        "Reviewed",
        "Closed",
    ]
    if status not in valid_statuses:
        logger.warning(
            "update_incident_spreadsheet_error",
            channel=channel_name,
            status=status,
            error="Invalid status",
        )
        return False
    sheet_name = "Sheet1"
    sheet = dict(sheets.get_values(INCIDENT_LIST, range=sheet_name))
    values = sheet.get("values", [])
    if len(values) == 0:
        logger.warning(
            "update_incident_spreadsheet_error",
            channel=channel_name,
            status=status,
            error="No values found in the sheet",
        )
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


def return_channel_name(input_str: str):
    # return the channel name without the incident- prefix and appending a # to the channel name
    prefix = "incident-"
    dev_prefix = prefix + "dev-"
    if input_str.startswith(dev_prefix):
        return "#" + input_str[len(dev_prefix) :]
    if input_str.startswith(prefix):
        return "#" + input_str[len(prefix) :]
    return input_str


def get_incidents_from_sheet(days=0) -> list:
    """Get incidents from Google Sheet"""
    date_lookback = datetime.datetime.now() - datetime.timedelta(days=days)
    date_lookback_str = date_lookback.strftime("%Y-%m-%d")
    incidents = sheets.get_sheet(INCIDENT_LIST, "Sheet1", includeGridData=True)
    if incidents and isinstance(incidents, dict):
        row_data = incidents.get("sheets")[0].get("data")[0].get("rowData")
        incidents_details = []
        for row in row_data[1:]:
            values = row.get("values")
            if not values or len(values) < 5:
                continue
            channel_url = values[4].get("hyperlink")
            channel_id = None
            if channel_url:
                match = re.search(
                    r"https://gcdigital\.slack\.com/archives/(\w+)", channel_url
                )
                if match:
                    channel_id = match.group(1)
            channel_name = values[4].get("formattedValue")
            if not channel_name:
                channel_name = "TBC"
            else:
                channel_name = channel_name[1:]
            incident_details = {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "name": values[1].get("formattedValue"),
                "user_id": "",
                "teams": [values[2].get("formattedValue")],
                "report_url": values[1].get("hyperlink"),
                "status": values[3].get("formattedValue"),
                "created_at": values[0].get("formattedValue"),
                "meet_url": "TBC",
            }
            if incident_details["channel_id"] is None:
                continue
            if days > 0:
                if incident_details["created_at"] < date_lookback_str:
                    continue
            incidents_details.append(incident_details)
        return incidents_details
    return []


def complete_incidents_details(client: WebClient, incidents: list[dict]):
    """Complete incidents details with channel info"""
    for incident in incidents:
        logger.info(
            "get_incident_details",
            channel_id=incident["channel_id"],
            channel_name=incident["channel_name"],
        )
        incident.update(get_incident_details(client, logger, incident))
        time.sleep(0.2)
    return incidents


def get_incident_details(client: WebClient, incident):
    """Get incident details from Slack"""
    max_retries = 5
    retry_attempts = 0
    while retry_attempts < max_retries:
        try:
            response = client.conversations_info(channel=incident["channel_id"])
            if response.get("ok"):
                channel_info = response.get("channel")
                incident["channel_name"] = channel_info.get("name")

                creator = channel_info.get("creator")
                if incident.get("user_id") == "":
                    incident["user_id"] = creator

                if (
                    "incident-dev-" in incident["channel_name"]
                    or "Development" in incident["teams"]
                ):
                    incident["environment"] = "dev"
                else:
                    incident["environment"] = "prod"
                created_at = channel_info.get("created", incident["created_at"])
                incident["created_at"] = str(created_at)

                is_archived = channel_info.get("is_archived")
                is_member = channel_info.get("is_member")

                meet_url = ""
                if not is_archived:
                    if not is_member:
                        client.conversations_join(channel=incident["channel_id"])
                    response = client.bookmarks_list(channel_id=incident["channel_id"])
                    if response["ok"]:
                        for item in range(len(response["bookmarks"])):
                            if response["bookmarks"][item]["title"] == "Meet link":
                                meet_url = response["bookmarks"][item]["link"]
                if meet_url:
                    incident["meet_url"] = meet_url
            return incident

        except SlackApiError as e:
            if retry_attempts < max_retries:
                retry_attempts += 1
                logger.warning(
                    "get_incident_details_error",
                    channel_id=incident["channel_id"],
                    error=str(e),
                    retry_attempts=retry_attempts,
                )
                time.sleep(10)
            else:
                logger.error(
                    "get_incident_details_max_retries",
                    channel_id=incident["channel_id"],
                    error=str(e),
                )
    return incident


def create_missing_incidents(incidents):
    """Create missing incidents"""
    count = 0
    for incident in incidents:
        incident_exists = db_operations.lookup_incident(
            "channel_id", incident["channel_id"]
        )
        if len(incident_exists) == 0:
            incident_data = {
                "channel_id": incident["channel_id"],
                "channel_name": incident["channel_name"],
                "name": incident["name"],
                "user_id": incident["user_id"],
                "teams": incident["teams"],
                "report_url": incident["report_url"],
                "status": incident["status"],
                "created_at": incident["created_at"],
                "meet_url": incident["meet_url"],
                "environment": incident["environment"],
            }
            incident_id = db_operations.create_incident(incident_data)
            if incident_id:
                message = "Automated import of the incident from the Google Sheet via the SRE Bot"
                db_operations.log_activity(incident_id, message)
            logger.info(
                "incident_created",
                incident_id=incident_id,
                incident_name=incident["name"],
            )
            count += 1
        else:
            logger.info(
                "incident_not_created",
                reason="Incident already exists",
                incident_id=incident_exists[0]["id"]["S"],
                incident_name=incident["name"],
            )
    return count


def current_time_est():
    est_tz = pytz.timezone("US/Eastern")
    current_time_est = datetime.datetime.now(est_tz)
    return current_time_est.strftime("%Y-%m-%d %H:%M:%S")


def store_update(incident_id, update_text):
    existing_incident = db_operations.lookup_incident("id", incident_id)
    # Check if the incident exists and has incident_updates
    current_updates = ""
    if existing_incident:
        existing_incident = existing_incident[0]
        if "incident_updates" in existing_incident and (
            existing_incident["incident_updates"]["L"] != []
        ):
            current_updates = existing_incident["incident_updates"]["L"][0]["S"]

    current_time_in_est = current_time_est() + " EST\n"
    update_text = current_time_in_est + update_text + "\n" + current_updates
    current_updates = [{"S": update_text}]

    response = dynamodb.update_item(
        TableName="incidents",
        Key={"id": {"S": incident_id}},
        UpdateExpression="SET incident_updates = :updates",
        ExpressionAttributeValues={":updates": {"L": current_updates}},
        ReturnValues="UPDATED_NEW",
    )
    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
        return response
    else:
        return None


def fetch_updates(channel_id):
    response = db_operations.lookup_incident("channel_id", channel_id)
    if response:
        response = response[0]
        if "incident_updates" in response and response["incident_updates"]["L"] != []:
            updates = [update["S"] for update in response["incident_updates"]["L"]]
            return updates
    else:
        return []
