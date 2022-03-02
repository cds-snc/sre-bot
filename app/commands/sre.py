import os

from commands import utils

from commands.helpers import incident_helper

help_text = """
\n `/sre help` - show this help text
\n `/sre incident` - lists incident commands
\n `/sre version` - show the version of the SRE Bot"""


def sre_command(ack, command, logger, respond):
    ack()
    logger.info("SRE command received: %s", command["text"])

    if command["text"] == "":
        respond("Type `/sre help` to see a list of commands.")
        return

    action, *args = utils.parse_command(command["text"])
    match action:
        case "help":
            respond(help_text)
        case "incident":
            resp = incident_helper.handle_incident_command(args)
            respond(resp)
        case "version":
            respond(f"SRE Bot version: {os.environ.get('GIT_SHA', 'unknown')}")
        case _:
            respond(
                f"Unknown command: {action}. Type `/sre help` to see a list of commands."
            )
