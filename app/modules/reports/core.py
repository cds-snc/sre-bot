from slack_bolt import Ack, Respond
from slack_sdk import WebClient
from structlog import get_logger

from modules.reports import google_groups

logger = get_logger()


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
    log = logger.bind(
        command_args=args,
        user_id=command["user_id"],
        channel_id=command["channel_id"],
    )
    if len(args) == 0:
        respond(help_text)
        return
    log.info("sre_reports_command_received", command_text=command["text"])

    action, *args = args
    log.info("reports_action_received", action=action, args=args)
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
