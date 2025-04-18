from slack_bolt import Ack, Respond
from slack_sdk import WebClient

from core.logging import get_module_logger
from modules.reports import google_groups

logger = get_module_logger()


help_text = """
\n `/sre reports help | aide`
\n      - show this help text
\n      - montre le texte d'aide
\n `/sre reports google-groups`
\n      - generate a Google Groups statistics report
\n      - générer un rapport statistique sur les groupes Google
\n `/sre reports google-groups-members`
\n      - generate a Google Groups Members report
\n      - générer un rapport sur les membres des groupes Google"""


def reports_command(args, ack: Ack, command, respond: Respond, client: WebClient, body):
    ack()
    if len(args) == 0:
        respond(help_text)
        return
    logger.info("SRE reports command received: %s", command["text"])

    action, *args = args
    logger.info("reports_action_received", action=action, args=args)
    match action:
        case "help" | "aide":
            respond(help_text)
        case "google-groups":
            google_groups.generate_report(args, respond)
        case "google-groups-members":
            google_groups.generate_group_members_report(args, respond)
        case _:
            respond(
                "Unknown command. Type `/sre reports help` for a list of commands.\nCommande inconnue. Tapez `/sre reports aide` pour voir une liste de commandes."
            )
