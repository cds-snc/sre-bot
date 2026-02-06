import json
import structlog

from slack_sdk.web import WebClient
from modules.aws import identity_center
from modules.permissions import handler as permissions
from integrations.slack import users as slack_users
from infrastructure.services import get_settings

logger = structlog.get_logger()

help_text = """
\n *AWS Users*:
\n • `/aws users <create|delete> [@username user.name@email.com]` - Provision or deprovision AWS users.
\n • `/aws users help` - Show this help text.
"""


def command_handler(client: WebClient, body, respond, args: str):
    """Handle the command.

    Args:
        client (WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
        args (list[str]): The list of arguments.
    """
    action: list[str] = args.pop(0) if args else ""
    match action:
        case "help" | "aide":
            respond(help_text)
        case "create" | "delete":
            # reinsert the action into the args list for the request_user_provisioning function
            args.insert(0, action)
            request_user_provisioning(client, body, respond, args)
        case _:
            respond("Invalid command. Type `/aws users help` for more information.")


def request_user_provisioning(client: WebClient, body, respond, args):
    """Request AWS user provisioning.

    This function processes a request to provision or deprovision AWS users.

    Args:
        client (SlackClient): The Slack client instance.
        body (dict): The request body.
        respond (function): The function to respond to the request.
        args (list): The list of arguments passed with the command.
    """
    settings = get_settings()
    requestor_email = slack_users.get_user_email_from_body(client, body)
    log = logger.bind(requestor_email=requestor_email)
    log.info("aws_users_provisioning_request_received")
    if permissions.is_user_member_of_groups(
        requestor_email, settings.aws_feature.AWS_ADMIN_GROUPS
    ):
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
        response = identity_center.provision_aws_users(operation, users_emails)
        respond(f"Request completed:\n{json.dumps(response, indent=2)}")
    else:
        respond(
            "This function is restricted to admins only. Please contact #sre-and-tech-ops for assistance."
        )

    log.info("aws_users_provisioning_request_completed")
