"""Testing AWS service (will be removed)"""

import logging

from integrations.aws import dynamodb

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(ack, client, body, respond, logger):
    ack()
    table = "webhooks"
    webhooks = dynamodb.scan(TableName=table, Select="ALL_ATTRIBUTES")
    webhook_id = webhooks[0]["id"]["S"]

    response = dynamodb.get_item(TableName=table, Key={"id": {"S": webhook_id}})

    logger.info(response)
