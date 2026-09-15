"""AWS Module

This module provides the following features:
- Health check of AWS accounts
- Provisioning and deprovisioning of AWS users
- Group management (syncing, listing)

"""

import structlog
from slack_bolt import Ack, App, Respond
from slack_sdk.web import WebClient

from infrastructure.slack.settings import get_slack_transport_settings
from integrations.slack import commands as slack_commands
from modules.aws import (
    aws_account_health,
    groups,
    lambdas,
    spending,
    users,
)

logger = structlog.get_logger()

help_text = """
\n `/aws users <operation> <user1> <user2> ...`
\n      - Provision or deprovision AWS users | Provisionner ou déprovisionner des utilisateurs AWS
\n        Supports multiple users for a single operation | Supporte plusieurs utilisateurs pour l'opération
\n        `<operation>`: `create` or/ou `delete`
\n        `<user>`: email address or Slack username of the user | adresse courriel ou identifiant Slack de l'utilisateur
\n        Usage: `/aws users create @username user.name@email.com`
\n `/aws groups <operation> <group1> <group2> ...`
\n      - Manage AWS groups | Gérer les groupes AWS
\n        `<operation>`: `sync`, `list`
\n        `<group>`: name of the group | nom du groupe (sync only)
\n        Usage: `/aws groups sync`, `/aws groups sync group-name` or/ou `/aws groups list`
\n `/aws lambdas <operation>`
\n     - Manage AWS Lambda functions | Gérer les fonctions Lambda AWS
\n `/aws help | aide`
\n      - Show this help text | montre le dialogue d'aide
\n `/aws health`
\n      - Query the health of an AWS account | Demander l'état de santé d'un compte AWS
"""


def register(bot: App) -> None:
    """AWS module registration.

    Args:
        bot (SlackBot): The SlackBot instance to which the module
            will be registered.
    """
    transport_settings = get_slack_transport_settings()
    bot.command(f"/{transport_settings.COMMAND_PREFIX}aws")(aws_command)
    bot.view("aws_health_view")(aws_account_health.health_view_handler)


def aws_command(ack: Ack, command, respond: Respond, client: WebClient, body) -> None:
    """AWS command handler.

    This function handles the `/aws` command by parsing the command text
    and executing the appropriate action.

    Args:
        ack (function): The function to acknowledge the command.
        command (dict): The command dictionary containing the command text.
        respond (function): The function to respond to the command.
        client (SlackClient): The Slack client instance.
        body (dict): The request
    """

    ack()
    log = logger.bind(
        user_id=command["user_id"],
        user_name=command["user_name"],
        channel_id=command["channel_id"],
        channel_name=command["channel_name"],
    )
    log.info(
        "aws_command_received",
        command=command["text"],
    )

    if command["text"] == "":
        respond("Type `/aws help` to see a list of commands. \n Tapez `/aws help` pour une liste des commandes")
        return

    action, *args = slack_commands.parse_command(command["text"])
    match action:
        case "help" | "aide":
            respond(help_text)
        case "health":
            aws_account_health.request_health_modal(client, body)
        case "users":
            users.command_handler(client, body, respond, args)
        case "groups":
            groups.command_handler(client, body, respond, args)
        case "lambda" | "lambdas":
            lambdas.command_handler(client, body, respond, args)
        case "spending":
            respond("Generating spending data...\nGénération des données de dépenses...")
            spending_df = spending.generate_spending_data()
            # An empty report is never written: it would replace the whole sheet.
            if spending_df is None or spending_df.empty:
                respond(
                    "Failed to generate spending data. Please try again later.\n"
                    "Échec de la génération des données de dépenses. Veuillez réessayer plus tard."
                )
                return
            if not spending.update_spending_data(spending_df):
                respond(
                    "Failed to update spending data. Please try again later.\n"
                    "Échec de la mise à jour des données de dépenses. Veuillez réessayer plus tard."
                )
                return
            respond("Spending data has been updated.\nLes données de dépenses ont été mises à jour.")
        case _:
            respond(
                f"Unknown command: `{action}`. Type `/aws help` to see a list of commands.\n"
                f"Commande inconnue: `{action}`. Tapez `/aws help` pour voir une liste des commandes."
            )
