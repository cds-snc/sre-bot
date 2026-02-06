import structlog

from datetime import datetime
from modules.aws import identity_center, ops_group_assignment
from modules.permissions import handler as permissions
from modules.provisioning import groups as provisioning_groups
from integrations.slack import users as slack_users
from infrastructure.services import get_settings

logger = structlog.get_logger()

help_text = """
\n *AWS Groups*:
\n • `/aws groups sync` - Sync groups from AWS Identity Center.
\n • `/aws groups list` - List all groups from AWS Identity Center.
"""


def command_handler(client, body, respond, args):
    """Handle the command.

    Args:
        client (Slack WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
        args (list[str]): The list of arguments.
    """
    action = args.pop(0) if args else ""

    match action:
        case "help" | "aide":
            respond(help_text)
        case "sync":
            request_groups_sync(client, body, respond, args)
        case "list":
            request_groups_list(client, body, respond, args)
        case "ops":
            request_groups_ops(client, body, respond, args)
        case _:
            respond("Invalid command. Type `/aws groups help` for more information.")


def request_groups_sync(client, body, respond, args):
    """Sync groups from AWS Identity Center.

        If additional arguments are provided, they will be used to filter the groups to sync.

    Args:
        client (Slack WebClient): The Slack client.
        body (dict): The request body.
        respond (function): The function to respond to the request.
        args (list[str]): The list of arguments.
    """
    settings = get_settings()
    requestor_email = slack_users.get_user_email_from_body(client, body)
    log = logger.bind(requestor_email=requestor_email)
    log.info("aws_groups_sync_request_received")
    if permissions.is_user_member_of_groups(
        requestor_email, settings.aws_feature.AWS_ADMIN_GROUPS
    ):
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
        log.info(
            "aws_groups_sync_request_processing",
            pre_processing_filters=len(pre_processing_filters),
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
        log.warning(
            "aws_groups_sync_request_denied",
            aws_admin_groups=settings.aws_feature.AWS_ADMIN_GROUPS,
        )
        respond("You do not have permission to sync groups.")
        return


def request_groups_list(client, body, respond, args):
    """List all groups from AWS Identity Center."""
    settings = get_settings()
    requestor_email = slack_users.get_user_email_from_body(client, body)
    log = logger.bind(requestor_email=requestor_email)
    log.info(
        "aws_groups_list_request_received",
    )
    if permissions.is_user_member_of_groups(
        requestor_email, settings.aws_feature.AWS_ADMIN_GROUPS
    ):
        respond("AWS Groups List request received.")
        log.info(
            "aws_groups_list_request_processing",
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
        log.warning(
            "aws_groups_list_request_denied",
            aws_admin_groups=settings.aws_feature.AWS_ADMIN_GROUPS,
        )
        respond("You do not have permission to list groups.")
        return


def request_groups_ops(client, body, respond, args):
    """Assign Ops group to all AWS accounts."""
    settings = get_settings()
    requestor_email = slack_users.get_user_email_from_body(client, body)
    log = logger.bind(requestor_email=requestor_email)
    log.info(
        "aws_ops_group_assignment_received",
    )
    if permissions.is_user_member_of_groups(
        requestor_email, settings.aws_feature.AWS_ADMIN_GROUPS
    ):
        respond("AWS Ops Group Assignment request received.")
        log.info(
            "aws_ops_group_assignment_processing",
        )
        response = ops_group_assignment.execute()
        if not response:
            respond("⚠️ AWS Ops Group Assignment feature is disabled.")
            return
        if response["status"] == "success":
            respond(f"✅ *Success*: {response['message']}")
        elif response["status"] == "failed":
            respond(f"❌ *Error*: {response['message']}")
        elif response["status"] == "ok":
            respond(f"ℹ️ *Info*: {response['message']}")
        else:
            respond(f"⚠️ {response['message']}")
    else:
        log.warning(
            "aws_ops_group_assignment_request_denied",
            aws_admin_groups=settings.aws_feature.AWS_ADMIN_GROUPS,
        )
        respond("You do not have permission to assign Ops group.")
        return
