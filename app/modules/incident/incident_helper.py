import re
from collections.abc import Callable
from datetime import datetime

from slack_bolt import Ack, App, Respond
from slack_sdk import WebClient
from structlog import get_logger

from features.incident.common.settings import get_incident_core_settings
from features.incident.core.adapters import google_docs as incident_drive
from integrations.slack import (
    channels as slack_channels,
)
from integrations.slack import (
    commands as slack_commands,
)
from modules.incident import (
    incident_conversation,
    incident_folder,
    schedule_retro,
)

INCIDENT_CHANNELS_PATTERN = r"^incident-\d{4}-"

UPDATES_RETIRED_POINTER = (
    "`/sre incident updates` has been retired. "
    "Use `/sre incident status-update` to draft, review and approve a public status update."
    "\n\n"
    "`/sre incident updates` a été retirée. "
    "Utilisez `/sre incident status-update` pour rédiger, réviser et approuver une mise à jour publique."
)

logger = get_logger()

help_text = """
*SRE Incident Management*

Usage:
`/sre incident [<resource>] <action> [options] [arguments]`

*Resources:*
• channels     - Manage incident channels
• products     - Manage incident products (aka folders)
• roles        - Manage incident roles
• status       - Update the incident status

*Incident-level actions (no resource):*
• close        - Close the current incident
• list         - List incidents or resources
• summarize    - Summarize the channel to catch up someone joining the incident
• draft        - Draft an incident report from the channel into a new document
• help         - Show this help message
• schedule     - Schedule an event for the incident
• show         - Show details of the current incident

*Examples:*
- `/sre incident list --stale`
- `/sre incident close`
- `/sre incident show`
- `/sre incident summarize`
- `/sre incident summarize --since 30m --limit 100`
- `/sre incident summarize --since 2h --limit 100`
- `/sre incident draft`
- `/sre incident products create "foo bar"`
- `/sre incident schedule retro`
- `/sre incident status update Ready to be Reviewed`
- `/sre incident status-update`

*Legacy commands (will be deprecated after 2025-11-01):*
• create-folder
• list-folders
• stale

_For details on each resource, use:_
`/sre incident <resource> help`
"""

help_text_fr = """
*Gestion des Incidents IFS:*

Utilisation:
`/sre incident [<ressource>] <action> [options] [arguments]`

*Ressources:*
• channels     - Gérer les canaux d'incidents
• products     - Gérer les produits d'incidents (dossiers)
• roles        - Gérer les rôles d'incidents
• status       - Mettre à jour l'état d'un incident

*Actions pour l'incident (sans ressource):*
• close        - Clore l'incident en cours
• list         - Lister les incidents ou ressources
• summarize    - Résumer le canal pour informer une personne rejoignant l'incident
• draft        - Rédiger une ébauche de rapport d'incident à partir du canal
• help         - Afficher ce message d'aide
• schedule     - Planifier un événement pour l'incident
• show         - Afficher les détails de l'incident en cours

*Exemples:*
- `/sre incident list --stale`
- `/sre incident close`
- `/sre incident show`
- `/sre incident summarize`
- `/sre incident summarize --since 30m --limit 100`
- `/sre incident summarize --since 2h --limit 100`
- `/sre incident draft`
- `/sre incident products create "foo bar"`
- `/sre incident schedule retro`
- `/sre incident status update Ready to be Reviewed`
- `/sre incident status-update`

*Commandes obsolètes (seront supprimées après le 2025-11-01):*
• create-folder
• list-folders
• stale

_Pour les détails sur chaque resource, utilisez:_
`/sre incident <resource> help`
"""


def register(bot: App):
    """Incident module registration.
    Args:
        bot (SlackBot): The SlackBot instance to which the module will be registered.
    """
    bot.action("add_folder_metadata")(incident_folder.add_folder_metadata)
    bot.action("view_folder_metadata")(incident_folder.view_folder_metadata)
    bot.view("view_folder_metadata_modal")(incident_folder.list_folders_view)
    bot.view("add_metadata_view")(incident_folder.save_metadata)
    bot.action("delete_folder_metadata")(incident_folder.delete_folder_metadata)
    bot.view("view_save_event")(schedule_retro.handle_schedule_retro_submit)
    bot.action("confirm_click")(schedule_retro.confirm_click)
    bot.action("user_select_action")(schedule_retro.incident_selected_users_updated)
    bot.action("archive_channel")(incident_conversation.archive_channel_action)
    bot.event("reaction_added", matchers=[incident_conversation.is_floppy_disk])(incident_conversation.handle_reaction_added)
    bot.event("reaction_removed", matchers=[incident_conversation.is_floppy_disk])(incident_conversation.handle_reaction_removed)
    bot.event("reaction_added")(incident_conversation.just_ack_the_rest_of_reaction_events)
    bot.event("reaction_removed")(incident_conversation.just_ack_the_rest_of_reaction_events)


def get_incident_actions() -> dict[str, Callable]:
    """Returns a dictionary mapping incident subcommands to their handler functions."""
    return {
        "help": handle_help,
        "aide": handle_help,
        "list": handle_list,
        "schedule": handle_schedule,
        # legacy commands
        "create-folder": handle_legacy_create_folder,
        "list-folders": handle_legacy_list_folders,
        "stale": handle_legacy_stale,
    }


def get_resource_handlers():
    """Returns a dictionary mapping resources to their handler functions."""
    return {
        "channels": handle_channels,
        "product": handle_products,
        "updates": handle_updates,
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
        action = args_list.pop(0) if args_list else "help"
        resource_handler: Callable = resource_handlers[resource]
        resource_handler(client, body, respond, ack, action, args_list, flags)
    elif first_arg in incident_actions:
        # this is to handle if the argument is a valid action on the incident itself
        action = first_arg
        if action == "aide":
            args_list = ["fr"] + args_list
        action_handler: Callable = incident_actions[action]
        action_handler(client, body, respond, ack, args_list, flags)
    else:
        if first_arg:
            respond(f"Unknown command: {first_arg}. Type `/sre incident help` to see a list of commands.")
        else:
            respond("Please provide a valid command. Type `/sre incident help` to see a list of commands.")


def handle_help(_client, _body, respond, _ack, args, _flags) -> None:
    """Handle help command."""
    if args and args[0].lower() in ["fr", "aide"]:
        respond(help_text_fr)
    else:
        respond(help_text)


def handle_list(client, body, respond, ack, args, _flags):
    """Handle list command."""
    list_help_text = """`/sre incident list [options]`

*Options:*
• `active` — lists all active incidents (default; not stale or archived)
• `stale` — lists all incidents older than 14 days with no activity

Use `/sre incident help` to see a list of commands."""
    try:
        option = args.pop(0)
    except IndexError:
        option = None
    match option:
        case "active":
            respond("Upcoming feature: list all active incidents.")
        case "stale":
            stale_incidents(client, body, ack)
        case _:
            respond(list_help_text)


def handle_schedule(client, body, respond, ack, args, _flags):
    """Handle the schedule command"""
    schedule_help_text = """`/sre incident schedule [options]`

*Options:*
• `retro` — schedule a retrospective for the incident

Use `/sre incident help` to see a list of commands."""
    try:
        option = args.pop(0)
    except IndexError:
        option = "retro"  # default to retro if no option is provided
    match option:
        case "retro":
            schedule_retro.open_incident_retro_modal(client, body, ack)
        case _:
            respond(schedule_help_text)


# resource level actions


def handle_channels(_client, _body, respond, _ack, action, _args, _flags):
    """Handle the channels command."""
    channels_help_text = """`/sre incident channels <action> [options] [arguments]`

*Actions:*
• `<Upcoming feature>` — manage incident channels"""
    match action:
        case _:
            respond(channels_help_text)


def handle_products(client, body, respond, ack, action, args, flags):
    """Handle the products command."""
    product_help_text = """`/sre incident products <action> [options] [arguments]`

*Actions:*
• `create <product_name>` — create a new product name to be referenced in the incident resources
  _Tip: Use quotes for multi-word product names: `create "product name"`_
• `list` — list all products currently available in the incident resources

Use `/sre incident help` to see a list of commands."""
    match action:
        case "create":
            name = " ".join(args)
            if not name:
                respond("Please provide a product name using `create <product_name>`")
                return
            folder = incident_drive.create_folder(name, get_incident_core_settings().folder_id)
            folder_name = None
            if folder:
                folder_name = folder.get("name")
            if folder_name:
                respond(f"Product `{folder_name}` created.")
            else:
                respond(f"Failed to create product `{name}`.")
        case "list":
            incident_folder.list_folders_view(client, body, ack)
        case _:
            respond(product_help_text)


def handle_updates(client, body, respond, ack, action, _args, _flags):
    """Answer every `/sre incident updates` request with the retired-command pointer."""
    respond(UPDATES_RETIRED_POINTER)


def handle_legacy_create_folder(client, body, respond, ack, args, _flags):
    """Handle the legacy create-folder command."""
    respond(
        "The `/sre incident create-folder` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident create folder <folder_name>` instead."
    )
    action = "create"
    handle_products(client, body, respond, ack, action, args, _flags)


def handle_legacy_list_folders(client, body, respond, ack, _args, flags):
    """Handle the legacy list-folders command."""
    respond(
        "The `/sre incident list-folders` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident list --folders` instead."
    )
    action = "list"
    handle_products(client, body, respond, ack, action, [], flags)


def handle_legacy_stale(client, body, respond, ack, _args, _flags):
    """Handle the legacy stale command."""
    respond(
        "The `/sre incident stale` command is deprecated and will be discontinued after 2025-11-01. Please use `/sre incident list --stale` instead."
    )
    stale_incidents(client, body, ack)


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

    placeholder_modal = client.views_open(trigger_id=body["trigger_id"], view=placeholder)

    # stale_channels = get_stale_channels(client)
    stale_channels = slack_channels.get_stale_channels(client, INCIDENT_CHANNELS_PATTERN)

    blocks = {
        "type": "modal",
        "callback_id": "stale_incidents_view",
        "title": {"type": "plain_text", "text": "SRE - Stale incidents"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [item for sublist in list(map(channel_item, stale_channels)) for item in sublist],
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
                    "text": (channel["topic"]["value"] if channel["topic"]["value"] else "No information available"),
                }
            ],
        },
        {"type": "divider"},
    ]


def parse_incident_datetime_string(datetime_string: str) -> str:
    pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}$"

    if re.match(pattern, datetime_string):
        parsed_datetime = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M:%S.%f")
        return parsed_datetime.strftime("%Y-%m-%d %H:%M")
    else:
        return "Unknown"


def convert_timestamp(timestamp: str) -> str:
    try:
        datetime_str = datetime.fromtimestamp(float(timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        datetime_str = "Unknown"
    return datetime_str
