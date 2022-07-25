import os

from commands import utils

from commands.helpers import geolocate_helper, incident_helper, webhook_helper

help_text = """
\n `/sre help` - show this help text | montre le texte d'aide
\n `/sre geolocate <ip>` - geolocate an IP address | géolocaliser une adresse IP
\n `/sre incident` - lists incident commands | lister les commandes d'incidents
\n `/sre webhooks` - lists webhook commands | lister les commandes de liens de rappel HTTP
\n `/sre version` - show the version of the SRE Bot | montre la version du bot SRE"""


def sre_command(ack, command, logger, respond, client, body):
    ack()
    logger.info("SRE command received: %s", command["text"])

    if command["text"] == "":
        respond("Type `/sre help` to see a list of commands.")
        return

    action, *args = utils.parse_command(command["text"])
    match action:
        case "help":
            respond(help_text)
        case "geolocate":
            if len(args) == 0:
                respond("Please provide an IP address. | "
                "SVP fournir une adresse IP")
                return
            geolocate_helper.geolocate(args, respond)
        case "incident":
            incident_helper.handle_incident_command(args, client, body, respond, ack)
        case "webhooks":
            webhook_helper.handle_webhook_command(args, client, body, respond)
        case "version":
            respond(f"SRE Bot version: {os.environ.get('GIT_SHA', 'unknown')}")
        case _:
            respond(
                f"Unknown command: `{action}`. Type `/sre help` to see a list of commands. \nCommande inconnue: `{action}`. Entrez `/sre help` pour une liste des commandes valides"
            )
