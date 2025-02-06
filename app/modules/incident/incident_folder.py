"""Module for managing SRE incident folders in Google Drive.

Includes functions to manage the folders, the metadata, and the list of incidents in a Google Sheets spreadsheet.
"""

import datetime
import os
import logging
import re
import uuid
from slack_sdk.web import WebClient
from slack_bolt import Ack
from integrations.google_workspace import google_drive, sheets
from integrations.aws import dynamodb

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
    valid_statuses = [
        "In Progress",
        "Open",
        "Ready to be Reviewed",
        "Reviewed",
        "Closed",
    ]
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
            else:
                incidents_details.append(incident_details)
        return incidents_details
    return []


def complete_incidents_details(client: WebClient, logger, incidents):
    """Complete incidents details with channel info"""
    for incident in incidents:
        response = client.conversations_info(channel=incident["channel_id"])
        if response.get("ok"):
            channel_info = response.get("channel")
            incident["channel_name"] = channel_info.get("name")

            if (
                "incident-dev-" in incident["channel_name"]
                or "Development" in incident["teams"]
            ):
                incident["environment"] = "dev"
            else:
                incident["environment"] = "prod"
            logger.info(f"incident environment: {incident['environment']}")
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
    return incidents


def create_missing_incidents(logger, incidents):
    """Create missing incidents"""
    count = 0
    for incident in incidents:
        incident_exists = lookup_incident("channel_id", incident["channel_id"])
        if len(incident_exists) == 0:
            incident_id = create_incident(
                channel_id=incident["channel_id"],
                channel_name=incident["channel_name"],
                name=incident["name"],
                user_id=incident["user_id"],
                teams=incident["teams"],
                report_url=incident["report_url"],
                status=incident["status"],
                created_at=incident["created_at"],
                meet_url=incident["meet_url"],
                environment=incident["environment"],
            )
            logger.info(f"created incident: {incident['name']}: {incident_id}")
            count += 1
        else:
            logger.info(
                f"incident {incident['name']} already exists: {incident_exists[0]['id']['S']}"
            )
    return count


def create_incident(
    channel_id,
    channel_name,
    name,
    user_id,
    teams,
    report_url,
    status="Open",
    meet_url=None,
    created_at=None,
    incident_commander=None,
    operations_lead=None,
    severity=None,
    start_impact_time=None,
    end_impact_time=None,
    detection_time=None,
    retrospective_url=None,
    environment="prod",
):
    if not created_at:
        created_at = str(datetime.datetime.now().timestamp())
    id = str(uuid.uuid4())
    incident_data = {
        "id": {"S": id},
        "created_at": {"S": created_at},
        "channel_id": {"S": channel_id},
        "channel_name": {"S": channel_name},
        "name": {"S": name},
        "status": {"S": status},
        "user_id": {"S": user_id},
        "teams": {"SS": teams},
        "report_url": {"S": report_url},
        "meet_url": {"S": meet_url},
        "environment": {"S": environment},
    }
    for key, value in [
        ("incident_commander", incident_commander),
        ("operations_lead", operations_lead),
        ("severity", severity),
        ("start_impact_time", start_impact_time),
        ("end_impact_time", end_impact_time),
        ("detection_time", detection_time),
        ("retrospective_url", retrospective_url),
    ]:
        if value:
            incident_data[key] = {"S": value}

    response = dynamodb.put_item(
        TableName="incidents",
        Item=incident_data,
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        logging.info("Created incident %s", id)
        return id
    return None


def list_incidents(select="ALL_ATTRIBUTES", **kwargs):
    """List all incidents in the incidents table."""
    return dynamodb.scan(TableName="incidents", Select=select, **kwargs)


def update_incident_field(id, field, value, type="S"):
    """Update an attribute in an incident item.

    Default type is string, but it can be changed to other types like N for numbers, SS for string sets, etc.

    Reference: https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/dynamodb.html#DynamoDB.Client.update_item
    """
    expression_attribute_names = {f"#{field}": field}
    expression_attribute_values = {f":{field}": {type: value}}

    response = dynamodb.update_item(
        TableName="incidents",
        Key={"id": {"S": id}},
        UpdateExpression=f"SET #{field} = :{field}",
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
    )
    if response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200:
        return response
    else:
        return None


def get_incident(id):
    return dynamodb.get_item(TableName="incidents", Key={"id": {"S": id}})


def get_incident_by_channel_id(channel_id) -> dict | None:
    """Get an incident by its channel ID.

    Args:
        channel_id (str): The channel ID.

    Returns:
        dict: The incident item. None if not found.
    """
    incidents = lookup_incident("channel_id", channel_id)
    if len(incidents) > 0:
        return incidents[0]
    return None


def lookup_incident(field, value, field_type="S"):
    """Lookup incidents by a specific field value."""
    return dynamodb.scan(
        TableName="incidents",
        FilterExpression=f"{field} = :{field}",
        ExpressionAttributeValues={f":{field}": {f"{field_type}": value}},
    )
