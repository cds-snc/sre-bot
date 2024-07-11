import os
from modules.aws import identity_center
from modules.permissions import handler as permissions
from integrations.slack import users as slack_users


AWS_ADMIN_GROUPS = os.environ.get("AWS_ADMIN_GROUPS", "sre-ifs@cds-snc.ca").split(",")


def request_groups_sync(client, body, respond, args, logger):
    """Sync groups from AWS Identity Center."""
    requestor_email = slack_users.get_user_email_from_body(client, body)
    if permissions.is_user_member_of_groups(requestor_email, AWS_ADMIN_GROUPS):
        respond("Groups synchronization request sent.")
        identity_center.synchronize(
            enable_user_create=False,
            enable_membership_create=True,
            enable_membership_delete=True,
        )
    else:
        respond("You do not have permission to sync groups.")
        return
    logger.info("Provisioning AWS Identity Center")
