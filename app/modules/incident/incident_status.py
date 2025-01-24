from datetime import datetime
import logging
import re
from slack_sdk import WebClient
from slack_bolt import Respond
from integrations.google_workspace import google_docs
from modules.incident import incident_document, incident_folder


def update_status(
    client: WebClient,
    respond: Respond,
    status: str,
    channel_id: str,
    channel_name: str,
    user_id: str,
    incident_id: str | None = None,
):

    document_id = ""
    try:
        response = client.bookmarks_list(channel_id=channel_id)
        if response["ok"]:
            for item in range(len(response["bookmarks"])):
                if response["bookmarks"][item]["title"] == "Incident report":
                    document_id = google_docs.extract_google_doc_id(
                        response["bookmarks"][item]["link"]
                    )
    except Exception as e:
        warning_message = f"Could not get bookmarks for channel {channel_name}: {e}"
        logging.warning(warning_message)
        respond(warning_message)

    if document_id != "":
        try:
            incident_document.update_incident_document_status(document_id, status)
        except Exception as e:
            warning_message = f"Could not update the incident status in the document for channel {channel_name}: {e}"
            logging.warning(warning_message)
            respond(warning_message)
    else:
        warning_message = f"No bookmark link for the incident document found for channel {channel_name}"
        logging.warning(warning_message)
        respond(warning_message)

    try:
        incident_folder.update_spreadsheet_incident_status(
            incident_folder.return_channel_name(channel_name), status
        )
        if incident_id:
            incident_folder.update_incident_field(incident_id, "status", status)
    except Exception as e:
        warning_message = f"Could not update the incident status in the spreadsheet for channel {channel_name}: {e}"
        logging.warning(warning_message)
        respond(warning_message)

    try:
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> has updated the incident status to {status}.",
        )
    except Exception as e:
        warning_message = f"Could not post the incident status update to the channel {channel_name}: {e}"
        logging.warning(warning_message)
        respond(warning_message)


def incident_information_view(incident):
    logging.info(f"Loading Status View for:\n{incident}")
    incident_name = incident.get("channel_name", "Unknown").get("S", "Unknown")
    incident_id = incident.get("id", "Unknown").get("S", "Unknown")
    incident_status = incident.get("status", "Unknown").get("S", "Unknown")
    incident_created_at = parse_incident_datetime_string(
        incident.get("created_at", {}).get("S", "Unknown")
    )
    incident_start_impact_time = parse_incident_datetime_string(
        incident.get("start_impact_time", {}).get("S", "Unknown")
    )
    incident_end_impact_time = parse_incident_datetime_string(
        incident.get("end_impact_time", {}).get("S", "Unknown")
    )
    incident_detection_time = parse_incident_datetime_string(
        incident.get("detection_time", {}).get("S", "Unknown")
    )
    return {
        "type": "modal",
        "callback_id": "incident_information_view",
        "title": {"type": "plain_text", "text": "Incident Information", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": incident_name,
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*ID*: " + incident_id,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Status*:\n" + incident_status,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "click_me_123",
                    "action_id": "update_status",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Time Created*:\n" + incident_created_at,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Detection Time*:\n" + incident_detection_time,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "click_me_123",
                    "action_id": "update_detection_time",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Start of Impact*:\n" + incident_start_impact_time,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "click_me_123",
                    "action_id": "update_start_impact_time",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*End of Impact*:\n" + incident_end_impact_time,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "click_me_123",
                    "action_id": "update_end_impact_time",
                },
            },
        ],
    }


def update_field_view(action):
    logging.info(f"Loading Update Field View for {action}")
    return {
        "type": "modal",
        "title": {"type": "plain_text", "text": "Incident Information", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": action,
                    "emoji": True,
                },
            }
        ],
    }


def parse_incident_datetime_string(datetime_string: str) -> str:
    pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}$"

    if re.match(pattern, datetime_string):
        parsed_datetime = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M:%S.%f")
        return parsed_datetime.strftime("%Y-%m-%d %H:%M")
    else:
        return "Unknown"
