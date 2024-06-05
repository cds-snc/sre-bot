"""Testing AWS service (will be removed)"""
import logging
from modules.aws import identity_center

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(ack, client, body, respond):
    ack()
    response = identity_center.synchronize(
        enable_user_create=False, enable_membership_create=False
    )
    if not response:
        respond("Sync failed.")
    else:
        respond("Sync successful.")
