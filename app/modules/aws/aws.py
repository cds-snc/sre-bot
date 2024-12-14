"""AWS Module

This module provides the following features:
- Access to AWS accounts
- Health check of AWS accounts
- Provisioning and deprovisioning of AWS users
- Group management (syncing, listing)

"""

import os
from slack_bolt import App, Ack, Respond
from slack_sdk.web import WebClient
from logging import Logger

from integrations.aws.organizations import get_account_id_by_name
from integrations.aws import identity_store
from integrations.slack import commands as slack_commands
from modules.aws import aws_access_requests, aws_account_health, groups, users, lambdas

PREFIX = os.environ.get("PREFIX", "")
AWS_ADMIN_GROUPS = os.environ.get("AWS_ADMIN_GROUPS", "sre-ifs@cds-snc.ca").split(",")

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
\n
\n (currently disabled)
\n `/aws access`
\n      - starts the process to access an AWS account | débute le processus pour accéder à un compte AWS
"""


def register(bot: App) -> None:
    """AWS module registration.

    Args:
        bot (SlackBot): The SlackBot instance to which the module will be registered.
    """
    bot.command(f"/{PREFIX}aws")(aws_command)
    bot.view("aws_access_view")(aws_access_requests.access_view_handler)
    bot.view("aws_health_view")(aws_account_health.health_view_handler)


def aws_command(
    ack: Ack, command, logger: Logger, respond: Respond, client: WebClient, body
) -> None:
    """AWS command handler.

    This function handles the `/aws` command by parsing the command text and executing the appropriate action.

    Args:
        ack (function): The function to acknowledge the command.
        command (dict): The command dictionary containing the command text.
        logger (Logger): The logger instance.
        respond (function): The function to respond to the command.
        client (SlackClient): The Slack client instance.
        body (dict): The request
    """

    ack()
    logger.info("AWS command received: %s", command["text"])

    if command["text"] == "":
        respond(
            "Type `/aws help` to see a list of commands. \n Tapez `/aws help` pour une liste des commandes"
        )
        return

    action, *args = slack_commands.parse_command(command["text"])
    match action:
        case "help" | "aide":
            respond(help_text)
        case "access":
            aws_access_requests.request_access_modal(client, body)
        case "health":
            aws_account_health.request_health_modal(client, body)
        case "users":
            users.command_handler(client, body, respond, args, logger)
        case "groups":
            groups.command_handler(client, body, respond, args, logger)
        case "lambda" | "lambdas":
            lambdas.command_handler(client, body, respond, args, logger)
        case _:
            respond(
                f"Unknown command: `{action}`. Type `/aws help` to see a list of commands.\n"
                f"Commande inconnue: `{action}`. Tapez `/aws help` pour voir une liste des commandes."
            )


def request_aws_account_access(
    account_name, rationale, start_date, end_date, user_email, access_type
):
    """
    Request AWS account access for a user.

    This function initiates a request for access to an AWS account for a specified user.
    It performs the following steps:
    1. Retrieves the account ID associated with the given account name.
    2. Retrieves the user ID associated with the given user email.
    3. Creates an AWS access request with the provided details.

    Args:
        account_name (str): The name of the AWS account to which access is requested.
        rationale (str): The reason for requesting access to the AWS account.
        start_date (datetime): The start date and time for the requested access period.
        end_date (datetime): The end date and time for the requested access period.
        user_email (str): The email address of the user requesting access.
        access_type (str): The type of access requested (e.g., 'read', 'write').

    Returns:
        bool: True if the access request was successfully created, False otherwise.
    """
    account_id = get_account_id_by_name(account_name)
    user_id = identity_store.get_user_id(user_email)
    return aws_access_requests.create_aws_access_request(
        account_id,
        account_name,
        user_id,
        user_email,
        start_date,
        end_date,
        access_type,
        rationale,
    )
