"""SRE Module

This module contains the main command for the SRE bot. It is responsible for handling the `/sre` command and its subcommands.
"""

import os

from modules.incident import incident_helper
from modules.sre import geolocate_helper, webhook_helper
from modules.dev import aws_dev, google
from integrations.slack import commands as slack_commands

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
\n      - montre la version du bot SRE"""

PREFIX = os.environ.get("PREFIX", "")


def register(bot):
    bot.command(f"/{PREFIX}sre")(sre_command)


def sre_command(ack, command, logger, respond, client, body):
    ack()
    logger.info("SRE command received: %s", command["text"])

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
        case "version":
            respond(f"SRE Bot version: {os.environ.get('GIT_SHA', 'unknown')}")
        case "google":
            if PREFIX == "dev-":
                google.google_service_command(ack, client, body, respond, logger)
            else:
                respond("This command is only available in the dev environment.")
            return
        case "aws":
            if PREFIX == "dev-":
                aws_dev.aws_dev_command(ack, client, body, respond)
            else:
                respond("This command is only available in the dev environment.")
            return
        case _:
            respond(
                f"Unknown command: `{action}`. Type `/sre help` to see a list of commands. \nCommande inconnue: `{action}`. Entrez `/sre help` pour une liste des commandes valides"
            )
