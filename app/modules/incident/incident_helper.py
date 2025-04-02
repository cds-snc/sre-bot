from datetime import datetime
import json
import re
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
    information_display,
    information_update,
)
from core.config import settings
from core.logging import get_module_logger

INCIDENT_CHANNELS_PATTERN = r"^incident-\d{4}-"
SRE_DRIVE_ID = settings.feat_incident.SRE_DRIVE_ID
SRE_INCIDENT_FOLDER = settings.feat_incident.SRE_INCIDENT_FOLDER
VALID_STATUS = [
    "In Progress",
    "Open",
    "Ready to be Reviewed",
    "Reviewed",
    "Closed",
]

logger = get_module_logger()

help_text = """
\n `/sre incident`
\n      - opens a modal to show and update the incident information
\n      - ouvre une boîte de dialogue pour afficher et mettre à jour les informations sur l'incident
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
    bot.view("view_save_event")(schedule_retro.handle_schedule_retro_submit)
    bot.action("confirm_click")(schedule_retro.confirm_click)
    bot.action("user_select_action")(schedule_retro.incident_selected_users_updated)
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
    bot.action("update_incident_field")(information_update.open_update_field_view)
    bot.view("update_field_modal")(information_update.handle_update_field_submission)


def handle_incident_command(
    args,
    client: WebClient,
    body,
    respond: Respond,
    ack: Ack,
):
    """Handle the /sre incident command."""
    logger.info(
        "sre_incident_command_received",
        args=args,
    )
    # If no arguments are provided, open the update status view
    if len(args) == 0:
        information_display.open_incident_info_view(client, body, respond)
        return
    action, *args = args
    match action:
        case "create-folder":
            name = " ".join(args)
            folder = google_drive.create_folder(name, SRE_INCIDENT_FOLDER)
            folder_name = None
            if isinstance(folder, dict):
                folder_name = folder.get("name", None)
            if folder_name:
                respond(f"Folder `{folder_name}` created.")
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
            schedule_retro.open_incident_retro_modal(client, body, ack)
            # retro.schedule_incident_retro(client, body, ack, logger)
        case "status":
            handle_update_status_command(client, body, respond, ack, args)
        case "add_summary":
            open_updates_dialog(client, body, ack)
        case "summary":
            display_current_updates(client, body, respond, ack)
        case _:
            respond(
                f"Unknown command: {action}. Type `/sre incident help` to see a list of commands."
            )


def close_incident(client: WebClient, body, ack, respond):
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
        logger.exception(
            "client_conversations_error", channel_id=channel_id, error=str(e)
        )
        return

    if not channel_name.startswith("incident-"):
        try:
            client.chat_postEphemeral(
                text=f"Channel {channel_name} is not an incident channel. Please use this command in an incident channel.",
                channel=channel_id,
                user=user_id,
            )
        except Exception as e:
            logger.exception(
                "client_post_ephemeral_error",
                channel_id=channel_id,
                user_id=user_id,
                error=str(e),
            )
        return

    incident_status.update_status(
        client,
        respond,
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
        logger.exception(
            "client_post_message_error",
            channel_id=channel_id,
            user_id=user_id,
            error=str(e),
        )

    # archive the channel
    try:
        client.conversations_archive(channel=channel_id)
        logger.info(
            "incident_channel_archived",
            channel_id=channel_id,
            channel_name=channel_name,
            user_id=user_id,
        )
        log_to_sentinel("incident_channel_archived", body)
    except Exception as e:
        logger.exception(
            "client_conversations_archive_error",
            channel_id=channel_id,
            user_id=user_id,
            error=str(e),
        )
        error_message = (
            f"Could not archive the channel {channel_name} due to error: {e}"
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
            status,
            body["channel_id"],
            body["channel_name"],
            user_id,
        )


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
