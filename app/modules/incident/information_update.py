from datetime import datetime
import json
import logging
from slack_bolt import Ack
from slack_sdk import WebClient
from models.incidents import Incident
from modules.incident import db_operations, information_display


def open_update_field_view(client: WebClient, body, ack: Ack):
    """Open the view to update the incident field"""
    ack()
    action = body["actions"][0]["value"]
    incident_data = json.loads(body["view"]["private_metadata"])
    view = update_field_view(action, incident_data)
    client.views_push(
        view_id=body["view"]["id"], view=view, trigger_id=body["trigger_id"]
    )


def update_field_view(action, incident_data):
    logging.info("Loading Update Field View for action: %s", action)
    date_actions = {
        "detection_time",
        "start_impact_time",
        "end_impact_time",
    }
    if action in date_actions:
        now = datetime.now()
        if incident_data[action] != "Unknown":
            now = datetime.fromtimestamp(float(incident_data[action]))
        initial_date = now.strftime("%Y-%m-%d")
        initial_time = now.strftime("%H:%M")
        return {
            "type": "modal",
            "callback_id": "update_field_modal",
            "title": {
                "type": "plain_text",
                "text": "Incident Information",
                "emoji": True,
            },
            "submit": {"type": "plain_text", "text": "Submit", "emoji": True},
            "close": {"type": "plain_text", "text": "OK", "emoji": True},
            "private_metadata": json.dumps(
                {"action": action, "incident_data": incident_data}
            ),
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": action,
                        "emoji": True,
                    },
                },
                {
                    "type": "input",
                    "block_id": "date_input",
                    "element": {
                        "type": "datepicker",
                        "initial_date": initial_date,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select a date",
                        },
                        "action_id": "date_picker",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Select a date",
                    },
                },
                {
                    "type": "input",
                    "block_id": "time_input",
                    "element": {
                        "type": "timepicker",
                        "initial_time": initial_time,
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select time",
                            "emoji": True,
                        },
                        "action_id": "time_picker",
                    },
                    "label": {
                        "type": "plain_text",
                        "text": "Select time",
                        "emoji": True,
                    },
                },
            ],
        }
    else:
        return {
            "type": "modal",
            "title": {
                "type": "plain_text",
                "text": "Incident Information",
                "emoji": True,
            },
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


def handle_update_field_submission(client: WebClient, body, ack: Ack, view, logger):
    ack()
    user_id = body["user"]["id"]

    private_metadata = json.loads(view["private_metadata"])
    action = private_metadata["action"]
    incident_data = private_metadata["incident_data"]
    incident_id = incident_data["id"]
    channel_id = incident_data["channel_id"]

    date = view["state"]["values"]["date_input"]["date_picker"]["selected_date"]
    time = view["state"]["values"]["time_input"]["time_picker"]["selected_time"]
    timestamp = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").timestamp()

    field_map = {
        "detection_time",
        "start_impact_time",
        "end_impact_time",
    }

    if action in field_map:
        db_operations.update_incident_field(
            logger, incident_id, action, str(timestamp), user_id, type="S"
        )
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> has updated the field {action} to {date} {time}",
        )

        incident_data[action] = str(timestamp)
        view = information_display.incident_information_view(Incident(**incident_data))
        client.views_update(view_id=body["view"]["root_view_id"], view=view)

    else:
        logger.error("Unknown action: %s", action)
