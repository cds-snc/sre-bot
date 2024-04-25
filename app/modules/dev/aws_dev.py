"""Testing AWS service (will be removed)"""
import json
import logging
from modules.aws import sync_identity_center


from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(client, body, respond):
    response = sync_identity_center.synchronize()
    logger.info(json.dumps(response, indent=2))
    if not response:
        respond("No groups found.")
        return
    respond(json.dumps(response, indent=2))
