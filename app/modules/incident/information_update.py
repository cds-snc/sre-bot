from datetime import datetime
import json
import logging
from slack_bolt import Ack
from slack_sdk import WebClient
from models.incidents import Incident
from modules.incident import db_operations, information_display

FIELD_SCHEMA = {
    "detection_time": {"type": "datetime"},
    "start_impact_time": {"type": "datetime"},
    "end_impact_time": {"type": "datetime"},
    "retrospective_url": {"type": "text"},
    "status": {
        "type": "dropdown",
        "options": [
            "Open",
            "In Progress",
            "Ready to be Reviewed",
            "Reviewed",
            "Closed",
        ],
    },
}


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
    """Update the incident field view based on the action clicked by the user.
    Will return the default view if the action is not recognized,
    or the view associated with the field type."""
    logging.info("Loading Update Field View for action: %s", action)
    if action not in FIELD_SCHEMA:
        return generate_default_field_update_view(action)
    field_info = FIELD_SCHEMA[action]
    if field_info["type"] == "datetime":
        return generate_date_field_update_view(action, incident_data)
    if field_info["type"] == "text":
        return generate_text_field_update_view(action, incident_data)
    if field_info["type"] == "dropdown":
        return generate_drop_down_field_update_view(
            action,
            incident_data,
            field_info["options"],
        )


def generate_default_field_update_view(action):
    """Generate the default view for updating the incident field, displaying the action name as read-only"""
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


def generate_date_field_update_view(action, incident_data):
    """Generate the view for updating the incident field with a date picker for fields that require a date"""
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


def generate_text_field_update_view(action, incident_data):
    """Generate the view for updating the incident field with a text input for fields that require text"""
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
                "block_id": "plain_text_input",
                "element": {
                    "type": "plain_text_input",
                    "initial_value": (
                        incident_data[action] if incident_data[action] else ""
                    ),
                    "action_id": "text_input",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Enter text",
                },
            },
        ],
    }


def generate_drop_down_field_update_view(action, incident_data, options):
    """Generate the view for updating the incident field with a drop-down menu for fields that require a selection"""
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
                "block_id": "drop_down_input",
                "element": {
                    "type": "static_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Select an item",
                    },
                    "initial_option": {
                        "text": {"type": "plain_text", "text": incident_data[action]},
                        "value": incident_data[action],
                    },
                    "options": [
                        {
                            "text": {"type": "plain_text", "text": option},
                            "value": option,
                        }
                        for option in options
                    ],
                    "action_id": "static_select",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Select an item",
                },
            },
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

    if action not in FIELD_SCHEMA or not FIELD_SCHEMA[action]["type"]:
        logger.error("Unsupported action: %s", action)
        return

    field_info = FIELD_SCHEMA.get(action, None)
    # if not field_info or not field_info["type"]:
    #     logger.error("Unknown field: %s", action)
    #     return

    value = None
    value_type = None
    message = f"<@{user_id}> has updated the field {action} to "
    match field_info["type"]:
        case "datetime":
            date = view["state"]["values"]["date_input"]["date_picker"]["selected_date"]
            time = view["state"]["values"]["time_input"]["time_picker"]["selected_time"]
            value = str(
                datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M").timestamp()
            )
            value_type = "S"
            message += f"{date} {time}"
        case "text":
            value = view["state"]["values"]["plain_text_input"]["text_input"]["value"]
            value_type = "S"
            message += value if value else "Unknown"
        case "dropdown":
            value = view["state"]["values"]["drop_down_input"]["static_select"][
                "selected_option"
            ]["value"]
            value_type = "S"
            message += value if value else "Unknown"
        case _:
            logger.error("Unknown field type: %s", field_info["type"])
            return
    if value and value_type:
        db_operations.update_incident_field(
            logger, incident_id, action, value, user_id, type=value_type
        )
        client.chat_postMessage(
            channel=channel_id,
            text=message,
        )

        incident_data[action] = value
        view = information_display.incident_information_view(Incident(**incident_data))
        client.views_update(view_id=body["view"]["root_view_id"], view=view)
