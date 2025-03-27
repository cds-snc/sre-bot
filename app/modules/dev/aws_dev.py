"""Testing AWS service (will be removed)"""

from modules.incident import db_operations


def aws_dev_command(ack, client, body, respond, logger):
    ack()

    incidents = db_operations.list_incidents()
    logger.info("aws_dev_command_completed", payload=incidents)
    if len(incidents) == 0:
        respond("No incidents found")
        return
