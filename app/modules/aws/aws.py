"""AWS Module

This module provides the following features:
- Access to AWS accounts
- Health check of AWS accounts
- Provisioning and deprovisioning of AWS users
- Group management (syncing, listing)

"""

import json
import os

from modules.aws import aws_sso, aws_account_health, aws_access_requests
from integrations.slack import commands as slack_commands, users as slack_users
from integrations.aws.organizations import get_account_id_by_name
from modules.permissions import handler as permissions
from modules.aws.identity_center import provision_aws_users
from modules.aws import groups

PREFIX = os.environ.get("PREFIX", "")
AWS_ADMIN_GROUPS = os.environ.get("AWS_ADMIN_GROUPS", "sre-ifs@cds-snc.ca").split(",")

help_text = """
\n `/aws user <operation> <user1> <user2> ...`
\n      - Provision or deprovision AWS users | Provisionner ou déprovisionner des utilisateurs AWS
\n        Supports multiple users for a single operation | Supporte plusieurs utilisateurs pour l'opération
\n        `<operation>`: `create` or/ou `delete`
\n        `<user>`: email address or Slack username of the user | adresse courriel ou identifiant Slack de l'utilisateur
\n        Usage: `/aws user create @username user.name@email.com`
\n `/aws help | aide`
\n      - Show this help text | montre le dialogue d'aide
\n
\n (currently disabled)
\n `/aws access`
\n      - starts the process to access an AWS account | débute le processus pour accéder à un compte AWS
\n `/aws health`
\n      - Query the health of an AWS account | Demander l'état de santé d'un compte AWS
"""


def register(bot):
    """AWS module registration.

    Args:
        bot (SlackBot): The SlackBot instance to which the module will be registered.
    """
    bot.command(f"/{PREFIX}aws")(aws_command)
    bot.view("aws_access_view")(aws_access_requests.access_view_handler)
    bot.view("aws_health_view")(health_view_handler)


def aws_command(ack, command, logger, respond, client, body) -> None:
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
            request_health_modal(client, body)
        case "user":
            request_user_provisioning(client, body, respond, args, logger)
        case "groups":
            groups.command_handler(client, body, respond, args, logger)
        case _:
            respond(
                f"Unknown command: `{action}`. Type `/aws help` to see a list of commands.\n"
                f"Commande inconnue: `{action}`. Tapez `/aws help` pour voir une liste des commandes."
            )


def health_view_handler(ack, body, logger, client):
    ack()

    account_id = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["value"]

    account_name = body["view"]["state"]["values"]["account"]["account"][
        "selected_option"
    ]["text"]["text"]

    account_info = aws_account_health.get_account_health(account_id)

    blocks = {
        "type": "modal",
        "callback_id": "health_view",
        "title": {"type": "plain_text", "text": "AWS - Health Check"},
        "close": {"type": "plain_text", "text": "Close"},
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Health check for *{account_name}*: ({account_id})",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""
*Cost:*

{account_info['cost']['last_month']['start_date']} - {account_info['cost']['last_month']['end_date']}: ${account_info['cost']['last_month']['amount']} USD
{account_info['cost']['current_month']['start_date']} - {account_info['cost']['current_month']['end_date']}: ${account_info['cost']['current_month']['amount']} USD
                        """,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"""
*Security:*

{"✅" if account_info['security']['config'] == 0 else "❌"} Config ({account_info['security']['config']} issues)\n
{"✅" if account_info['security']['guardduty'] == 0 else "❌"} GuardDuty ({account_info['security']['guardduty']} issues)\n
{"✅" if account_info['security']['securityhub'] == 0 else "❌"} SecurityHub ({account_info['security']['securityhub']} issues)\n
                        """,
                },
            },
        ],
    }

    client.views_open(
        trigger_id=body["trigger_id"],
        view=blocks,
    )


def request_health_modal(client, body):
    accounts = aws_account_health.get_accounts()
    options = [
        {
            "text": {"type": "plain_text", "text": value},
            "value": key,
        }
        for key, value in accounts.items()
    ]
    client.views_open(
        trigger_id=body["trigger_id"],
        view={
            "type": "modal",
            "callback_id": "aws_health_view",
            "title": {"type": "plain_text", "text": "AWS - Account health"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "block_id": "account",
                    "type": "input",
                    "element": {
                        "type": "static_select",
                        "placeholder": {
                            "type": "plain_text",
                            "text": "Select an account to view | Choisissez un compte à afficher",
                        },
                        "options": options,
                        "action_id": "account",
                    },
                    "label": {"type": "plain_text", "text": "Account", "emoji": True},
                }
            ],
        },
    )


def request_user_provisioning(client, body, respond, args, logger):
    requestor_email = slack_users.get_user_email_from_body(client, body)
    if permissions.is_user_member_of_groups(requestor_email, AWS_ADMIN_GROUPS):
        operation = args[0]
        users_emails = args[1:]
        users_emails = [
            (
                slack_users.get_user_email_from_handle(client, email)
                if email.startswith("@")
                else email
            )
            for email in users_emails
        ]
        response = provision_aws_users(operation, users_emails)
        respond(f"Request completed:\n{json.dumps(response, indent=2)}")
    else:
        respond(
            "This function is restricted to admins only. Please contact #sre-and-tech-ops for assistance."
        )

    logger.info("Completed user provisioning request")


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
    user_id = aws_sso.get_user_id(user_email)
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
