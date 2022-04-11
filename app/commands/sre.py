import os

from commands import utils

from commands.helpers import geolocate_helper, incident_helper, webhook_helper

help_text = """
\n `/sre help` - show this help text
\n `/sre geolocate <ip>` - geolocate an IP address
\n `/sre incident` - lists incident commands
\n `/sre webhooks` - lists webhook commands
\n `/sre version` - show the version of the SRE Bot"""


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
                respond("Please provide an IP address.")
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
                f"Unknown command: {action}. Type `/sre help` to see a list of commands."
            )
