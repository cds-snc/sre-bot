import json
from decimal import Decimal
from typing import List, Type

import uuid
from datetime import datetime
from pydantic import BaseModel
from boto3.dynamodb.types import TypeDeserializer

from models import model_utils
from models.webhooks import WebhookPayload, AwsSnsPayload, AccessRequest, UpptimePayload
from integrations.aws import dynamodb
from core.logging import get_module_logger

logger = get_module_logger()

table = "webhooks"


def create_webhook(channel, user_id, name, hook_type="alert"):
    id = str(uuid.uuid4())
    response = dynamodb.put_item(
        TableName=table,
        Item={
            "id": {"S": id},
            "channel": {"S": channel},
            "name": {"S": name},
            "created_at": {"S": str(datetime.now())},
            "active": {"BOOL": True},
            "user_id": {"S": user_id},
            "invocation_count": {"N": "0"},
            "acknowledged_count": {"N": "0"},
            "hook_type": {"S": hook_type},
        },
    )

    if response["ResponseMetadata"]["HTTPStatusCode"] == 200:
        return id
    else:
        return None


def delete_webhook(id):
    response = dynamodb.delete_item(TableName=table, Key={"id": {"S": id}})
    return response


def get_webhook(id):
    response = dynamodb.get_item(TableName=table, Key={"id": {"S": id}})
    if response:
        return response
    else:
        return None


def lookup_webhooks(field, value, field_type="S"):
    """Lookup webhooks by a specific field value."""
    return dynamodb.scan(
        TableName=table,
        FilterExpression=f"{field} = :{field}",
        ExpressionAttributeValues={f":{field}": {f"{field_type}": value}},
    )


def increment_acknowledged_count(id):
    response = dynamodb.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET acknowledged_count = acknowledged_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )
    return response


def increment_invocation_count(id):
    response = dynamodb.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET invocation_count = invocation_count + :inc",
        ExpressionAttributeValues={":inc": {"N": "1"}},
    )
    return response


def list_all_webhooks():
    response = dynamodb.scan(TableName=table, Select="ALL_ATTRIBUTES")
    return response


def revoke_webhook(id):
    response = dynamodb.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={":active": {"BOOL": False}},
    )
    return response


# function to return the status of the webhook (ie if it is active or not). If active, return True, else return False
def is_active(id):
    response = dynamodb.get_item(TableName=table, Key={"id": {"S": id}})
    if response:
        return response["active"]["BOOL"]
    else:
        return False


def toggle_webhook(id):
    response = dynamodb.update_item(
        TableName=table,
        Key={"id": {"S": id}},
        UpdateExpression="SET active = :active",
        ExpressionAttributeValues={
            ":active": {"BOOL": not get_webhook(id)["active"]["BOOL"]}
        },
    )
    return response


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def deserialize_webhook(webhook):
    deserialize = TypeDeserializer()
    deserialized_webhook = {k: deserialize.deserialize(v) for k, v in webhook.items()}
    return json.loads(json.dumps(deserialized_webhook, default=decimal_default))


def validate_string_payload_type(payload: str) -> tuple:
    """
    This function takes a string payload and returns the type of webhook payload it is based on the parameters it contains.

    Args:
        payload (str): The payload to validate.

    Returns:
        tuple: A tuple containing the type of payload and the payload dictionary. If the payload is invalid, both values are None.
    """

    payload_type = None
    payload_dict = None
    try:
        payload_dict = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("string_payload_validation_error", error="Invalid JSON payload")
        return None, None

    known_models: List[Type[BaseModel]] = [
        AwsSnsPayload,
        AccessRequest,
        UpptimePayload,
        WebhookPayload,
    ]
    model_params = model_utils.get_dict_of_parameters_from_models(known_models)

    max_matches = 0
    for model, params in model_params.items():
        matches = model_utils.has_parameters_in_model(params, payload_dict)
        if matches > max_matches:
            max_matches = matches
            payload_type = model

    if payload_type:
        return payload_type, payload_dict
    else:
        logger.warning(
            "string_payload_validation_error",
            error="Unknown payload type",
            payload=payload,
        )
        return None, None
