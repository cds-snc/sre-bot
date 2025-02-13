from datetime import datetime
import json
import logging
import os
import re
from boto3.dynamodb.types import TypeDeserializer
from slack_sdk import WebClient
from slack_bolt import Ack, Respond, App
from integrations.google_workspace import google_drive
from integrations.slack import channels as slack_channels, users as slack_users
from integrations.sentinel import log_to_sentinel
from modules.incident import (
    incident_status,
    incident_alert,
    incident_folder,
    incident_roles,
    incident_conversation,
    schedule_retro,
    db_operations,
)
from models.incidents import Incident

INCIDENT_CHANNELS_PATTERN = r"^incident-\d{4}-"
SRE_DRIVE_ID = os.environ.get("SRE_DRIVE_ID")
SRE_INCIDENT_FOLDER = os.environ.get("SRE_INCIDENT_FOLDER")
START_HEADING = "DO NOT REMOVE this line as the SRE bot needs it as a placeholder."
END_HEADING = "Trigger"
VALID_STATUS = [
    "In Progress",
    "Open",
    "Ready to be Reviewed",
    "Reviewed",
    "Closed",
]


help_text = """
\n `/sre incident create-folder <folder_name>`
\n      - create a folder for a team in the incident drive
\n      - créer un dossier pour une équipe dans le dossier d'incidents
\n `/sre incident help`
\n      - show this help text
\n      - afficher ce texte d'aide
\n `/sre incident list-folders`
\n      - list all folders in the incident drive
\n      - lister tous les dossiers dans le dossier d'incidents
\n `/sre incident roles`
\n      - manages roles in an incident channel
\n      - gérer les rôles dans un canal d'incident
\n  `/sre incident schedule`
\n      - schedules a 30 minute meeting a week into the future in everyone's calendars for the incident post mortem process.
\n      - planifie une réunion de 30 minutes une semaine dans le futur dans les calendriers de tout le monde pour le processus de post-mortem de l'incident.
\n `/sre incident close`
\n      - close the incident, archive the channel and update the incident spreadsheet and document
\n      - clôturer l'incident, archiver le canal et mettre à jour la feuille de calcul et le document de l'incident
\n `/sre incident stale`
\n      - lists all incidents older than 14 days with no activity
\n      - lister tous les incidents plus vieux que 14 jours sans activité
\n `/sre incident status <status>`
\n      - update the status of the incident with the provided status. Supported statuses are: Open, In Progress, Ready to be Reviewed, Reviewed, Closed
\n      - mettre à jour le statut de l'incident avec le statut fourni. Les statuts pris en charge sont : Open, In Progress, Ready to be Reviewed, Reviewed, Closed
\n `/sre incident add_summary`
\n      - encourages the IC to give freeform summary on what has been done to resolve the incident so far
\n      - encourage l'IC à donner un résumé libre sur ce qui a été fait pour résoudre l'incident jusqu'à présent
\n `/sre incident summary`
\n      - displays the summary of the incident
\n      - affiche le résumé de l'incident
"""


def register(bot: App):
    bot.action("handle_incident_action_buttons")(
        incident_alert.handle_incident_action_buttons
    )
    bot.action("add_folder_metadata")(incident_folder.add_folder_metadata)
    bot.action("view_folder_metadata")(incident_folder.view_folder_metadata)
    bot.view("view_folder_metadata_modal")(incident_folder.list_folders_view)
    bot.view("add_metadata_view")(incident_folder.save_metadata)
    bot.action("delete_folder_metadata")(incident_folder.delete_folder_metadata)
    bot.view("view_save_incident_roles")(incident_roles.save_incident_roles)
    bot.view("view_save_event")(schedule_retro.save_incident_retro)
    bot.action("confirm_click")(schedule_retro.confirm_click)
    bot.action("update_incident_field")(open_update_field_view)
    bot.action("archive_channel")(incident_conversation.archive_channel_action)
    bot.event("reaction_added", matchers=[incident_conversation.is_floppy_disk])(
        incident_conversation.handle_reaction_added
    )
    bot.event("reaction_removed", matchers=[incident_conversation.is_floppy_disk])(
        incident_conversation.handle_reaction_removed
    )
    bot.event("reaction_added")(
        incident_conversation.just_ack_the_rest_of_reaction_events
    )
    bot.event("reaction_removed")(
        incident_conversation.just_ack_the_rest_of_reaction_events
    )
    bot.view("incident_updates_view")(handle_updates_submission)
    bot.view("update_field_modal")(handle_update_field_submission)


def handle_incident_command(
    args, client: WebClient, body, respond: Respond, ack: Ack, logger
):
    """Handle the /sre incident command."""

    # If no arguments are provided, open the update status view
    if len(args) == 0:
        open_incident_info_view(client, body, ack, respond)
        return
    action, *args = args
    match action:
        case "create-folder":
            name = " ".join(args)
            folder = google_drive.create_folder(name, SRE_INCIDENT_FOLDER)
            if folder:
                respond(f"Folder `{folder['name']}` created.")
            else:
                respond(f"Failed to create folder `{name}`.")
        case "help":
            respond(help_text)
        case "list-folders":
            incident_folder.list_folders_view(client, body, ack)
        case "roles":
            incident_roles.manage_roles(client, body, ack, respond)
        case "close":
            close_incident(client, logger, body, ack, respond)
        case "stale":
            stale_incidents(client, body, ack)
        case "schedule":
            schedule_retro.schedule_incident_retro(client, body, ack)
        case "status":
            handle_update_status_command(client, logger, body, respond, ack, args)
        case "add_summary":
            open_updates_dialog(client, body, ack)
        case "summary":
            display_current_updates(client, body, respond, ack)
        case _:
            respond(
                f"Unknown command: {action}. Type `/sre incident help` to see a list of commands."
            )


def close_incident(client: WebClient, logger, body, ack, respond):
    ack()
    # get the current chanel id and name
    channel_id = body["channel_id"]
    channel_name = body["channel_name"]
    user_id = slack_users.get_user_id_from_request(body)
    incident_id = None
    incident = db_operations.get_incident_by_channel_id(channel_id)
    if incident:
        incident_id = incident.get("id", {}).get("S", None)
    # ensure the bot is actually in the channel before performing actions
    try:
        response = client.conversations_info(channel=channel_id)
        channel_info = response.get("channel", None)
        if channel_info is None or not channel_info.get("is_member", False):
            client.conversations_join(channel=channel_id)
    except Exception as e:
        logging.error("Failed to join the channel %s: %s", channel_id, e)
        return

    if not channel_name.startswith("incident-"):
        try:
            client.chat_postEphemeral(
                text=f"Channel {channel_name} is not an incident channel. Please use this command in an incident channel.",
                channel=channel_id,
                user=user_id,
            )
        except Exception as e:
            logging.error(
                "Could not post ephemeral message to user %s due to %s.", user_id, e
            )
        return

    incident_status.update_status(
        client,
        respond,
        logger,
        "Closed",
        channel_id,
        channel_name,
        user_id,
        incident_id,
    )

    # Need to post the message before the channel is archived so that the message can be delivered.
    try:
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> has archived this channel 👋",
        )
    except Exception as e:
        logging.error(
            "Could not post message to channel %s due to error: %s.", channel_name, e
        )

    # archive the channel
    try:
        client.conversations_archive(channel=channel_id)
        logging.info(
            "Channel %s has been archived by %s", channel_name, f"<@{user_id}>"
        )
        log_to_sentinel("incident_channel_archived", body)
    except Exception as e:
        error_message = (
            f"Could not archive the channel {channel_name} due to error: {e}"
        )
        logging.error(error_message)
        respond(error_message)


def stale_incidents(client: WebClient, body, ack: Ack):
    ack()

    placeholder = {
        "type": "modal",
        "callback_id": "stale_incidents_view",
        "title": {"type": "plain_text", "text": "SRE - Stale incidents"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Loading stale incident list ...(this may take a minute)",
                },
            }
        ],
    }

    placeholder_modal = client.views_open(
        trigger_id=body["trigger_id"], view=placeholder
    )

    # stale_channels = get_stale_channels(client)
    stale_channels = slack_channels.get_stale_channels(
        client, INCIDENT_CHANNELS_PATTERN
    )

    blocks = {
        "type": "modal",
        "callback_id": "stale_incidents_view",
        "title": {"type": "plain_text", "text": "SRE - Stale incidents"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            item
            for sublist in list(map(channel_item, stale_channels))
            for item in sublist
        ],
    }

    client.views_update(view_id=placeholder_modal["view"]["id"], view=blocks)


def channel_item(channel):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<#{channel['id']}>",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": (
                        channel["topic"]["value"]
                        if channel["topic"]["value"]
                        else "No information available"
                    ),
                }
            ],
        },
        {"type": "divider"},
    ]


def handle_update_status_command(
    client: WebClient, logger, body, respond: Respond, ack: Ack, args
):
    ack()
    status = str.join(" ", args)
    user_id = slack_users.get_user_id_from_request(body)
    valid_statuses = [
        "In Progress",
        "Open",
        "Ready to be Reviewed",
        "Reviewed",
        "Closed",
    ]
    if status not in valid_statuses:
        respond(
            "A valid status must be used with this command:\n"
            + ", ".join(valid_statuses)
        )
        return
    incident = db_operations.get_incident_by_channel_id(body["channel_id"])

    if not incident:
        respond(
            "No incident found for this channel. Will not update status in DB record."
        )
        return
    else:
        respond(f"Updating incident status to {status}...")

        incident_status.update_status(
            client,
            respond,
            logger,
            status,
            body["channel_id"],
            body["channel_name"],
            user_id,
        )


def open_incident_info_view(client: WebClient, body, ack: Ack, respond: Respond):
    """Open the incident information view. This view displays the incident details where certain fields can be updated."""
    incident = db_operations.get_incident_by_channel_id(body["channel_id"])
    if not incident:
        respond(
            "This is command is only available in incident channels. No incident records found for this channel."
        )
        return
    else:
        deserialize = TypeDeserializer()
        incident_data = {k: deserialize.deserialize(v) for k, v in incident.items()}
        view = incident_information_view(Incident(**incident_data))
        client.views_open(trigger_id=body["trigger_id"], view=view)


def open_update_field_view(client: WebClient, body, ack: Ack, respond: Respond):
    """Open the view to update the incident field"""
    ack()
    action = body["actions"][0]["value"]
    incident_data = json.loads(body["view"]["private_metadata"])
    view = update_field_view(action, incident_data)
    client.views_push(
        view_id=body["view"]["id"], view=view, trigger_id=body["trigger_id"]
    )


def incident_information_view(incident: Incident):
    """Create the view for the incident information modal. It should receive a valid Incident object"""
    created_at = "Unknown"
    impact_start_timestamp = "Unknown"
    impact_end_timestamp = "Unknown"
    detection_timestamp = "Unknown"
    if incident.created_at:
        created_at = convert_timestamp(incident.created_at)
    if incident.start_impact_time:
        impact_start_timestamp = convert_timestamp(incident.start_impact_time)
    if incident.end_impact_time:
        impact_end_timestamp = convert_timestamp(incident.end_impact_time)
    if incident.detection_time:
        detection_timestamp = convert_timestamp(incident.detection_time)

    incident_data = incident.model_dump()
    private_metadata = json.dumps(incident_data)

    return {
        "type": "modal",
        "callback_id": "incident_information_view",
        "title": {"type": "plain_text", "text": "Incident Information", "emoji": True},
        "close": {"type": "plain_text", "text": "OK", "emoji": True},
        "private_metadata": private_metadata,
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": incident.name,
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*ID*: " + incident.id,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Status*:\n" + incident.status,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "status",
                    "action_id": "update_incident_field",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Time Created*:\n" + created_at,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Detection Time*:\n" + detection_timestamp,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "detection_time",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Start of Impact*:\n" + impact_start_timestamp,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "click_me_123",
                    "action_id": "update_incident_field",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*End of Impact*:\n" + impact_end_timestamp,
                },
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Update", "emoji": True},
                    "value": "click_me_123",
                    "action_id": "update_incident_field",
                },
            },
        ],
    }


def update_field_view(action, incident_data):
    logging.info("Loading Update Field View for action: %s", action)
    # logging.info(json.dumps(incident_data, indent=2))
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
    logging.info("Body: %s", body)

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
        view = incident_information_view(Incident(**incident_data))
        client.views_update(view_id=body["view"]["root_view_id"], view=view)

    else:
        logger.error("Unknown action: %s", action)


def parse_incident_datetime_string(datetime_string: str) -> str:
    pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}$"

    if re.match(pattern, datetime_string):
        parsed_datetime = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M:%S.%f")
        return parsed_datetime.strftime("%Y-%m-%d %H:%M")
    else:
        return "Unknown"


def convert_timestamp(timestamp: str) -> str:
    try:
        datetime_str = datetime.fromtimestamp(float(timestamp)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except ValueError:
        datetime_str = "Unknown"
    return datetime_str


def open_updates_dialog(client: WebClient, body, ack: Ack):
    ack()
    channel_id = body["channel_id"]  # Extract channel_id directly from body
    incident = db_operations.get_incident_by_channel_id(channel_id)
    incident_id = incident.get("id", "Unknown").get("S", "Unknown")
    dialog = {
        "type": "modal",
        "callback_id": "incident_updates_view",
        "private_metadata": json.dumps(
            {
                "incident_id": incident_id,  # Set the incident_id here
                "channel_id": channel_id,
            }
        ),
        "title": {"type": "plain_text", "text": "SRE - Incident Updates"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "updates_block",
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "action_id": "updates_input",
                },
                "label": {
                    "type": "plain_text",
                    "text": "Enter your updates",
                },
            },
        ],
    }
    client.views_open(trigger_id=body["trigger_id"], view=dialog)


def handle_updates_submission(client: WebClient, ack, respond: Respond, view):
    ack()
    private_metadata = json.loads(view["private_metadata"])
    incident_id = private_metadata["incident_id"]
    updates_text = view["state"]["values"]["updates_block"]["updates_input"]["value"]
    incident_folder.store_update(incident_id, updates_text)
    channel_id = private_metadata["channel_id"]
    client.chat_postMessage(channel=channel_id, text="Summary has been updated.")


def display_current_updates(client: WebClient, body, respond: Respond, ack: Ack):
    ack()
    incident_id = body["channel_id"]
    updates = incident_folder.fetch_updates(incident_id)
    if updates:
        updates_text = "\n".join(updates)
        client.chat_postMessage(
            channel=incident_id, text=f"Current updates:\n{updates_text}"
        )
    else:
        respond("No updates found for this incident.")
