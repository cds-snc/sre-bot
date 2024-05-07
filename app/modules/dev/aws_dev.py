"""Testing AWS service (will be removed)"""
import logging
from modules.aws import identity_center

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(ack, client, body, respond):
    ack()
    response = identity_center.synchronize(enable_groups_sync=False)
    if not response:
        respond("No groups found.")
    else:
        message = ""
        if identity_center.DRY_RUN:
            message += "Dry run mode enabled.\n"
        if response["users"]:
            users_created, users_deleted = response["users"]
            message += "Users created:\n- " + "\n- ".join(users_created) + "\n"
            message += "Users deleted:\n- " + "\n- ".join(users_deleted) + "\n"
        else:
            message += "Users Sync Disabled.\n"
        if response["groups"]:
            groups_created, groups_deleted = response["groups"]
            message += (
                "Groups memberships created:\n- " + "\n- ".join(groups_created) + "\n"
            )
            message += (
                "Groups memberships deleted:\n- " + "\n- ".join(groups_deleted) + "\n"
            )
        else:
            message += "Groups Sync Disabled.\n"
        respond(message)
