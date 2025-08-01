"""SRE Module

This module contains the main command for the SRE bot. It is responsible for handling the `/sre` command and its subcommands.
"""

from slack_sdk import WebClient
from slack_bolt import Ack, Respond, App

from modules.incident import incident_helper
from modules.sre import geolocate_helper, webhook_helper
from modules.dev import core as dev_core
from modules.reports import core as reports
from integrations.slack import commands as slack_commands
from core.config import settings
from core.logging import get_module_logger

PREFIX = settings.PREFIX
GIT_SHA = settings.GIT_SHA

logger = get_module_logger()

help_text = """
\n `/sre help | aide`
\n      - show this help text
\n      - montre le texte d'aide
\n `/sre geolocate <ip>`
\n      - geolocate an IP address
\n      - géolocaliser une adresse IP
\n `/sre incident`
\n      - lists incident commands
\n      - lister les commandes d'incidents
\n `/sre webhooks`
\n      - lists webhook commands
\n      - lister les commandes de liens de rappel HTTP
\n `/sre version`
\n      - show the version of the SRE Bot
\n      - montre la version du bot SRE
\n `/sre reports`
\n      - lists reports commands
\n      - lister les commandes de rapports"""


def register(bot: App):
    bot.command(f"/{PREFIX}sre")(sre_command)


def sre_command(
    ack: Ack,
    command,
    respond: Respond,
    client: WebClient,
    body,
):
    ack()
    logger.info(
        "sre_command_received",
        command=command["text"],
        user_id=command["user_id"],
        user_name=command["user_name"],
        channel_id=command["channel_id"],
        channel_name=command["channel_name"],
    )

    if command["text"] == "":
        respond(
            "Type `/sre help` to see a list of commands.\nTapez `/sre aide` pour voir une liste de commandes"
        )
        return

    action, *args = slack_commands.parse_command(command["text"])
    match action:
        case "help" | "aide":
            respond(help_text)
        case "geolocate":
            if len(args) == 0:
                respond("Please provide an IP address.\n" "SVP fournir une adresse IP")
                return
            geolocate_helper.geolocate(args, respond)
        case "incident":
            incident_helper.handle_incident_command(args, client, body, respond, ack)
        case "webhooks":
            webhook_helper.handle_webhook_command(args, client, body, respond)
        case "test":
            dev_core.dev_command(ack, respond, client, body, args)
        case "version":
            respond(f"SRE Bot version: {GIT_SHA}")
        case "reports":
            reports.reports_command(args, ack, command, respond, client, body)
        case _:
            respond(
                f"Unknown command: `{action}`. Type `/sre help` to see a list of commands. \nCommande inconnue: `{action}`. Entrez `/sre help` pour une liste des commandes valides"
            )
