"""Testing AWS service (will be removed)"""

import json
import logging
from dotenv import load_dotenv

from modules.incident import db_operations

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(ack, client, body, respond, logger):
    ack()

    incidents = db_operations.list_incidents()
    logger.info(json.dumps(incidents, indent=2))
    if len(incidents) == 0:
        respond("No incidents found")
        return
