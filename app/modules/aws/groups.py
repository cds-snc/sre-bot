from datetime import datetime
from modules.aws import identity_center
from modules.permissions import handler as permissions
from modules.provisioning import groups as provisioning_groups
from integrations.slack import users as slack_users
from core.config import settings

AWS_ADMIN_GROUPS = settings.aws_feature.AWS_ADMIN_GROUPS

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
    """Sync groups from AWS Identity Center.

        If additional arguments are provided, they will be used to filter the groups to sync.

    Args:
        client (Slack WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
        args (list[str]): The list of arguments.
        logger (Logger): The logger.
    """
    requestor_email = slack_users.get_user_email_from_body(client, body)
    logger.info("aws_groups_sync_request_received", requestor_email=requestor_email)
    if permissions.is_user_member_of_groups(requestor_email, AWS_ADMIN_GROUPS):
        pre_processing_filters = (
            [
                lambda group, arg=arg: arg.lower()
                in group.get("DisplayName", "").lower()
                or arg.lower() in group.get("name", "").lower()
                for arg in args
            ]
            if args
            else []
        )
        logger.info(
            "aws_groups_sync_request_processing",
            requestor_email=requestor_email,
            pre_processing_filters=pre_processing_filters,
        )
        respond("AWS Groups Memberships Synchronization Initiated.")
        start_time = datetime.now()
        identity_center.synchronize(
            enable_users_sync=False,
            enable_user_create=False,
            enable_membership_create=True,
            enable_membership_delete=True,
            pre_processing_filters=pre_processing_filters,
        )
        end_time = datetime.now()
        time = end_time - start_time
        respond(
            f"AWS Groups Memberships Synchronization Completed in {time.total_seconds():.6f} seconds."
        )
    else:
        logger.warning(
            "aws_groups_sync_request_denied",
            requestor_email=requestor_email,
            aws_admin_groups=AWS_ADMIN_GROUPS,
            error="User does not have permission to sync groups.",
        )
        respond("You do not have permission to sync groups.")
        return


def request_groups_list(client, body, respond, args, logger):
    """List all groups from AWS Identity Center."""
    requestor_email = slack_users.get_user_email_from_body(client, body)
    logger.info(
        "aws_groups_list_request_received",
        requestor_email=requestor_email,
    )
    if permissions.is_user_member_of_groups(requestor_email, AWS_ADMIN_GROUPS):
        respond("AWS Groups List request received.")
        logger.info(
            "aws_groups_list_request_processing",
            requestor_email=requestor_email,
        )
        response = provisioning_groups.get_groups_from_integration(
            "aws_identity_center"
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
        logger.warning(
            "aws_groups_list_request_denied",
            requestor_email=requestor_email,
            aws_admin_groups=AWS_ADMIN_GROUPS,
            error="User does not have permission to list groups.",
        )
        respond("You do not have permission to list groups.")
        return
