"""Testing AWS service (will be removed)"""
import json
import logging
from modules.aws import identity_center

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(ack, client, body, respond):
    ack()
    response = identity_center.synchronize(enable_groups_sync=True)
    if not response:
        respond("No groups found.")
    else:
        logger.info(json.dumps(response, indent=2))
        # respond(json.dumps(response[0], indent=2))
