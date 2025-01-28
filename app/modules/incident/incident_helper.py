from datetime import datetime
import json
import logging
import os
import re
from slack_sdk import WebClient
from slack_bolt import Ack, Respond, App
from integrations.google_workspace import google_drive
from integrations.slack import channels as slack_channels
from integrations.sentinel import log_to_sentinel
from modules.incident import (
    incident_status,
    incident_alert,
    incident_folder,
    incident_roles,
    incident_conversation,
    schedule_retro,
)

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
    bot.action("archive_channel")(archive_channel_action)
    bot.view("view_save_incident_roles")(incident_roles.save_incident_roles)
    bot.view("view_save_event")(schedule_retro.save_incident_retro)
    bot.action("confirm_click")(schedule_retro.confirm_click)
    bot.action("update_status")(open_update_field_view)
    bot.action("update_detection_time")(open_update_field_view)
    bot.action("update_start_impact_time")(open_update_field_view)
    bot.action("update_end_impact_time")(open_update_field_view)
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


def handle_incident_command(args, client: WebClient, body, respond: Respond, ack: Ack):
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
            close_incident(client, body, ack, respond)
        case "stale":
            stale_incidents(client, body, ack)
        case "schedule":
            schedule_retro.schedule_incident_retro(client, body, ack)
        case "status":
            handle_update_status_command(client, body, respond, ack, args)
        case _:
            respond(
                f"Unknown command: {action}. Type `/sre incident help` to see a list of commands."
            )


def archive_channel_action(client: WebClient, body, ack, respond):
    ack()
    channel_id = body["channel"]["id"]
    action = body["actions"][0]["value"]
    channel_name = body["channel"]["name"]
    user = body["user"]["id"]

    # get the current chanel id and name and make up the body with those 2 values
    channel_info = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "user_id": user,
    }

    if action == "ignore":
        msg = (
            f"<@{user}> has delayed scheduling and archiving this channel for 14 days."
        )
        client.chat_update(
            channel=channel_id, text=msg, ts=body["message_ts"], attachments=[]
        )
        log_to_sentinel("incident_channel_archive_delayed", body)
    elif action == "archive":
        # Call the close_incident function to update the incident document to closed, update the spreadsheet and archive the channel
        close_incident(client, channel_info, ack, respond)
        # log the event to sentinel
        log_to_sentinel("incident_channel_archived", body)
    elif action == "schedule_retro":
        channel_info["trigger_id"] = body["trigger_id"]
        schedule_retro.schedule_incident_retro(client, channel_info, ack)
        # log the event to sentinel
        log_to_sentinel("incident_retro_scheduled", body)


def close_incident(client: WebClient, body, ack, respond):
    ack()
    # get the current chanel id and name
    channel_id = body["channel_id"]
    channel_name = body["channel_name"]
    user_id = body["user_id"]

    # ensure the bot is actually in the channel before performing actions
    try:
        response = client.conversations_info(channel=channel_id)
        channel_info = response.get("channel", None)
        if channel_info is None or not channel_info.get("is_member", False):
            client.conversations_join(channel=channel_id)
    except Exception as e:
        logging.error(f"Failed to join the channel {channel_id}: {e}")
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
                f"Could not post ephemeral message to user {user_id} due to {e}.",
            )
        return

    incident_status.update_status(
        client, respond, "Closed", channel_id, channel_name, user_id
    )

    # Need to post the message before the channel is archived so that the message can be delivered.
    try:
        client.chat_postMessage(
            channel=channel_id,
            text=f"<@{user_id}> has archived this channel 👋",
        )
    except Exception as e:
        logging.error(
            f"Could not post message to channel {channel_name} due to error: {e}.",
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
        logging.error(
            "Could not archive the channel %s due to error: %s", channel_name, e
        )
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
    client: WebClient, body, respond: Respond, ack: Ack, args
):
    ack()
    status = str.join(" ", args)
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
    incidents = incident_folder.lookup_incident("channel_id", body["channel_id"])
    if not incidents:
        respond(
            "No incident found for this channel. Will not update status in DB record."
        )
        return
    else:
        if len(incidents) > 1:
            respond(
                "More than one incident found for this channel. Will not update status in DB record."
            )
            return
        else:
            respond(f"Updating incident status to {status}...")

            incident_folder.update_incident_field(
                incidents[0]["id"]["S"], "status", status
            )

            incident_status.update_status(
                client,
                respond,
                status,
                body["channel_id"],
                body["channel_name"],
                body["user_id"],
            )


def open_incident_info_view(client: WebClient, body, ack: Ack, respond: Respond):

    incidents = incident_folder.lookup_incident("channel_id", body["channel_id"])
    if not incidents:
        respond(
            "This is command is only available in incident channels. No incident records found for this channel."
        )
        return
    else:
        if len(incidents) > 1:
            respond("More than one incident found for this channel.")
        else:
            view = incident_information_view(incidents[0])
            client.views_open(trigger_id=body["trigger_id"], view=view)


def open_update_field_view(client: WebClient, body, ack: Ack, respond: Respond):
    ack()
    logging.info("Opening field view")
    logging.info(json.dumps(body, indent=2))
    action = body["actions"][0]["action_id"]
    view = update_field_view(action)
    client.views_push(
        view_id=body["view"]["id"], view=view, trigger_id=body["trigger_id"]
    )


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
