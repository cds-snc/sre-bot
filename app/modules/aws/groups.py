import os
from modules.aws import identity_center
from modules.permissions import handler as permissions
from modules.provisioning import groups as provisioning_groups
from integrations.slack import users as slack_users

AWS_ADMIN_GROUPS = os.environ.get("AWS_ADMIN_GROUPS", "sre-ifs@cds-snc.ca").split(",")

help_text = """
\n *AWS Groups*:
\n • `/aws groups sync` - Sync groups from AWS Identity Center.
\n • `/aws groups list` - List all groups from AWS Identity Center.
"""


def command_handler(client, body, respond, args, logger):
    """Handle the command.

    Args:
        client (Slack WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
        args (list[str]): The list of arguments.
        logger (Logger): The logger.
    """
    action = args.pop(0) if args else ""

    match action:
        case "help" | "aide":
            respond(help_text)
        case "sync":
            request_groups_sync(client, body, respond, args, logger)
        case "list":
            request_groups_list(client, body, respond, args, logger)
        case _:
            respond("Invalid command. Type `/aws groups help` for more information.")


def request_groups_sync(client, body, respond, args, logger):
    """Sync groups from AWS Identity Center."""
    requestor_email = slack_users.get_user_email_from_body(client, body)
    if permissions.is_user_member_of_groups(requestor_email, AWS_ADMIN_GROUPS):
        logger.info("Synchronizing AWS Identity Center Groups.")
        respond("AWS Groups Memberships Synchronization Initiated.")
        identity_center.synchronize(
            enable_user_create=False,
            enable_membership_create=True,
            enable_membership_delete=True,
        )
    else:
        logger.error(f"User {requestor_email} does not have permission to sync groups.")
        respond("You do not have permission to sync groups.")
        return


def request_groups_list(client, body, respond, args, logger):
    """List all groups from AWS Identity Center."""
    requestor_email = slack_users.get_user_email_from_body(client, body)
    if permissions.is_user_member_of_groups(requestor_email, AWS_ADMIN_GROUPS):
        respond("AWS Groups List request received.")
        logger.info("Listing AWS Identity Center Groups.")
        response = provisioning_groups.get_groups_from_integration(
            "aws_identity_center", members_details=False
        )
        response.sort(key=lambda x: x["DisplayName"])
        formatted_string = "Groups found:\n"
        for group in response:
            members_count = 0
            if group.get("GroupMemberships"):
                members_count = len(group["GroupMemberships"])
            formatted_string += f" • {group['DisplayName']} ({members_count} members)\n"
        respond(formatted_string)
    else:
        respond("You do not have permission to list groups.")
        return
