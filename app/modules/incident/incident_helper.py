from datetime import datetime
from typing import Callable
import json
import re
from slack_sdk import WebClient
from slack_bolt import Ack, Respond, App
from integrations.google_workspace import google_drive
from integrations.slack import (
    channels as slack_channels,
    users as slack_users,
    commands as slack_commands,
)
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
*SRE Incident Management*

Usage:
`/sre incident [<resource>] <action> [options] [arguments]`

*Resources:*
• channel      - Manage incident channels
• product      - Manage incident products (folders)
• roles        - Manage incident roles
• updates      - Add or show incident updates
• status       - Update or show incident status

*Incident-level actions (no resource):*
• create       - Create a new incident
• close        - Close the current incident
• details      - Show details of the current incident
• list         - List incidents or resources
• help         - Show this help message
• schedule     - Schedule an event for the incident

*Examples:*
- `/sre incident create`
- `/sre incident channel list --stale`
- `/sre incident close`
- `/sre incident details`
- `/sre incident product create "foo bar"`
- `/sre incident schedule retro`
- `/sre incident status update Ready to be Reviewed`
- `/sre incident updates add "new update"`

*Legacy commands (will be deprecated after 2025-11-01):*
• summary
• add_summary
• create-folder
• list-folders
• stale

_For details on each subcommand, use:_  
`/sre incident <subcommand> help`

---

*Gestion des Incidents IFS:*

Utilisation:
`/sre incident [<ressource>] <action> [options] [arguments]`

*Ressources:*
• channel      - Gérer les canaux d'incidents
• product      - Gérer les produits d'incidents (dossiers)
• roles        - Gérer les rôles d'incidents
• updates      - Ajouter ou afficher des mises à jour d'incidents
• status       - Mettre à jour ou afficher l'état d'un incident

*Actions pour l'incident (sans ressource):*
• create       - Créer un nouvel incident
• close        - Clore l'incident en cours
• details      - Afficher les détails de l'incident en cours
• list         - Lister les incidents ou ressources
• help         - Afficher ce message d'aide

*Commandes obsolètes (seront supprimées après le 2025-11-01):*
• add_summary
• summary
• create-folder
• list-folders
• stale

_Pour les détails sur chaque sous-commande, utilisez:_
`/sre incident <sous-commande> help`
"""


def register(bot: App):
    """Incident module registration.
    Args:
        bot (SlackBot): The SlackBot instance to which the module will be registered.
    """
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


def get_incident_actions() -> dict[str, Callable]:
    """Returns a dictionary mapping incident subcommands to their handler functions."""
    return {
        "create": handle_create,
        "close": handle_close,
        "details": handle_details,
        "help": handle_help,
        "list": handle_list,
        "schedule": handle_schedule,
        # legacy commands
        "create-folder": handle_legacy_create_folder,
        "list-folders": handle_legacy_list_folders,
        "stale": handle_legacy_stale,
        "add_summary": handle_legacy_add_summary,
        "summary": handle_legacy_summary,
    }


def get_resource_handlers():
    """Returns a dictionary mapping resources to their handler functions."""
    return {
        "channel": handle_channel,
        "product": handle_product,
        "roles": handle_roles,
        "updates": handle_updates,
        "status": handle_status,
    }


def handle_incident_command(
    args: list[str],
    client: WebClient,
    body: dict,
    respond: Respond,
    ack: Ack,
):
    """Handle the /sre incident command."""
    logger.info(
        "sre_incident_command_received",
        args=args,
    )
    args_list, flags = slack_commands.parse_flags(args)
    try:
        first_arg = args_list.pop(0)
    except IndexError:
        first_arg = None
    resource_handlers = get_resource_handlers()
    incident_actions = get_incident_actions()
    if first_arg in resource_handlers:
        # this is to handle if the argument is a resource
        resource = first_arg
        if (
            resource == "status"
            and len(args_list) > 0
            and " ".join(args_list) in VALID_STATUS
        ):
            args_list.insert(0, "update")  # handle legacy command, to be deprecated
            respond(
                "The `/sre incident status <status>` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident status update <status>` instead."
            )
        action = args_list.pop(0) if len(args_list) > 1 else "help"
        resource_handler: Callable = resource_handlers.get(resource, handle_help)
        resource_handler(client, body, respond, ack, action, args_list, flags)
    elif first_arg in incident_actions:
        # this is to handle if the argument is a valid action on the incident itself
        action = first_arg
        action_handler: Callable = incident_actions.get(action, handle_help)
        action_handler(client, body, respond, ack, args_list, flags)
    else:
        if first_arg:
            respond(
                f"Unknown command: {first_arg}. Type `/sre incident help` to see a list of commands."
            )
        else:
            respond(
                "Please provide a valid command. Type `/sre incident help` to see a list of commands."
            )


def handle_help(_client, _body, respond, _ack, _args, _flags) -> None:
    """Handle help command."""
    respond(help_text)


def handle_details(client, body, respond, _ack, _args, _flags):
    """Handle details command."""
    information_display.open_incident_info_view(client, body, respond)


def handle_create(_client, _body, respond, _ack, args: list[str], _flags: dict):
    """Handle create command."""
    create_help_text = (
        "\n `/sre incident create [resource] [options]`"
        "\n"
        "\n*Resources*"
        "\n folder <folder_name>      - create a folder for a team in the incident drive"
        '\n          _Tip: Use quotes for multi-word folder names: `--folder "folder name"`_'
        "\n new [<incident_name>]        - create a new incident (upcoming feature)"
    )
    resource = args.pop(0)
    match resource:
        case "new":
            respond("Upcoming feature: create a new incident.")
            return
        case "folder":
            name = " ".join(args)
            if not name:
                respond("Please provide a folder name using --folder <folder_name>")
                return
            folder = google_drive.create_folder(name, SRE_INCIDENT_FOLDER)
            folder_name = None
            if isinstance(folder, dict):
                folder_name = folder.get("name", None)
            if folder_name:
                respond(f"Folder `{folder_name}` created.")
            else:
                respond(f"Failed to create folder `{name}`.")
        case _:
            respond(create_help_text)


def handle_close(client, body, respond, ack, args, flags):
    close_incident(client, body, ack, respond)


def handle_list(client, body, respond, ack, _args, flags):
    list_help_text = (
        "\n `/sre incident list --folders`"
        "\n      - lists all folders in the incident drive"
        "\n      - lister tous les dossiers dans le dossier d'incidents"
        "\n `/sre incident list --stale`"
        "\n      - lists all incidents older than 14 days with no activity"
        "\n      - lister tous les incidents plus vieux que 14 jours sans activité"
        "\n Use `/sre incident help` to see a list of commands."
    )
    if "folders" in flags:
        incident_folder.list_folders_view(client, body, ack)
    if "stale" in flags:
        stale_incidents(client, body, ack)
    else:
        respond(list_help_text)


def handle_updates(client, body, respond, ack, args, flags):
    """Handle the updates command."""
    if "--add" in flags:
        open_updates_dialog(client, body, ack)
    else:
        display_current_updates(client, body, respond, ack)


def handle_channel(client, body, respond, ack, action, args, flags):
    pass


def handle_product(client, body, respond, ack, action, args, flags):
    pass


def handle_schedule(client, body, respond, ack, args, flags):
    if not args:
        args = ["retro"]
    action = args[0]
    match action:
        case "retro":
            schedule_retro.open_incident_retro_modal(client, body, ack)
        case _:
            respond(
                f"Unknown schedule action: {action}. Currently, only 'retro' is supported."
            )


def handle_status(client, body, respond, ack, action, args, _flags):
    """Handle the status command."""
    status_help_text = (
        "\n `/sre incident status [options] [arguments]`"
        "\n"
        "\n*Options*"
        "\n show             - show the current incident status"
        "\n update <status>   - update the incident status to one of the valid statuses"
        "\n"
        "\n*Valid Statuses*"
        "\n" + ", ".join(VALID_STATUS)
    )
    match action:
        case "update":
            if args:
                handle_update_status_command(client, body, respond, ack, args)
            else:
                respond("Please provide a status to update.")
        case "show":
            respond("Upcoming feature: show current incident status.")
        case _:
            respond(status_help_text)


def handle_roles(client, body, respond, ack, _action, _args, _flags):
    incident_roles.manage_roles(client, body, ack, respond)


def handle_legacy_create_folder(client, body, respond, ack, args, _flags):
    """Handle the legacy create-folder command."""
    respond(
        "The `/sre incident create-folder` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident create folder <folder_name>` instead."
    )
    args.insert(0, "folder")
    handle_create(client, body, respond, ack, args, _flags)


def handle_legacy_list_folders(client, body, respond, ack, _args, flags):
    """Handle the legacy list-folders command."""
    respond(
        "The `/sre incident list-folders` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident list --folders` instead."
    )
    flags["folders"] = True
    handle_list(client, body, respond, ack, [], flags)


def handle_legacy_stale(client, body, respond, ack, _args, _flags):
    """Handle the legacy stale command."""
    respond(
        "The `/sre incident stale` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident list --stale` instead."
    )
    # Optionally, call the new handler logic:
    stale_incidents(client, body, ack)


def handle_legacy_add_summary(client, body, respond, ack, _args, _flags):
    """Handle the legacy add_summary command."""
    respond(
        "The `/sre incident add_summary` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident updates` instead."
    )
    open_updates_dialog(client, body, ack)


def handle_legacy_summary(client, body, respond, ack, _args, _flags):
    """Handle the legacy summary command."""
    respond(
        "The `/sre incident summary` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident updates` instead."
    )
    display_current_updates(client, body, respond, ack)


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
