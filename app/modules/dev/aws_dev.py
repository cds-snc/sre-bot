"""Testing AWS service (will be removed)"""

import datetime
import logging

# from modules.aws import dynamodb
from integrations.aws import dynamodb

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def aws_dev_command(ack, client, body, respond):
    ack()
    account_id = "283582579564"
    TableName = "aws_access_requests"
    KeyConditionExpression = "account_id = :account_id and created_at > :created_at"
    ExpressionAttributeValues = {
        ":account_id": {"S": account_id},
        ":created_at": {"N": str(datetime.datetime.now().timestamp() - (4 * 60 * 60))},
    }
    response = dynamodb.query(
        table_name=TableName,
        KeyConditionExpression=KeyConditionExpression,
        ExpressionAttributeValues=ExpressionAttributeValues,
    )
    if not response:
        respond("Sync failed. See logs")
    else:
        logger.info(response)
        respond("Sync successful.")
