import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from pydantic import BaseModel
from structlog import get_logger

from infrastructure.operations import OperationResult, OperationStatus
from models.webhooks import (
    AccessRequest,
    AwsSnsPayload,
    SimpleTextPayload,
    WebhookPayload,
)
from packages.aws_platform.adapters.dynamodb import DynamoDBAdapter, build_dynamodb_adapter
from utils import models as model_utils

logger = get_logger()

table = "webhooks"


class WebhookStoreUnavailableError(Exception):
    """Raised when the webhooks table cannot be read or updated.

    Carries the adapter's classification so callers can map it to a response
    (e.g. 503 with ``Retry-After``); the message stays generic and never includes
    provider error text.
    """

    def __init__(self, status: OperationStatus, error_code: str | None = None, retry_after: int | None = None) -> None:
        super().__init__("webhooks store unavailable")
        self.status = status
        self.error_code = error_code
        self.retry_after = retry_after


def _unavailable(result: OperationResult[Any]) -> WebhookStoreUnavailableError:
    """Build the store-unavailable error from a non-success adapter result."""
    return WebhookStoreUnavailableError(result.status, error_code=result.error_code, retry_after=result.retry_after)


def _failure_fields(result: OperationResult[Any]) -> dict[str, Any]:
    """Return the structured log fields describing a non-success adapter result."""
    return {"status": result.status.value, "error_code": result.error_code, "error": result.message}


def _unclassified_fields(exc: ClientError) -> dict[str, Any]:
    """Return the structured log fields for a ClientError the adapter did not classify."""
    error = exc.response.get("Error", {})
    return {"status": "unclassified", "error_code": error.get("Code"), "error": error.get("Message")}


def _get_item(adapter: DynamoDBAdapter, id: str) -> dict[str, Any] | None:
    """Read one webhook item; None when absent, raise when the read fails."""
    try:
        result = adapter.get_item(TableName=table, Key={"id": {"S": id}})
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_get_failed", webhook_id=id, **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
    if not result.is_success:
        logger.error("webhook_get_failed", webhook_id=id, **_failure_fields(result))
        raise _unavailable(result)
    return result.data


def create_webhook(channel: str, user_id: str, name: str, hook_type: str = "alert") -> str | None:
    """Create an active webhook and return its id, or None when the write fails."""
    adapter = build_dynamodb_adapter()
    id = str(uuid.uuid4())
    try:
        result = adapter.put_item(
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
    except ClientError as exc:
        logger.error("webhook_create_failed", **_unclassified_fields(exc))
        return None
    if not result.is_success:
        logger.error("webhook_create_failed", **_failure_fields(result))
        return None
    return id


def get_webhook(id: str) -> dict[str, Any] | None:
    """Return the webhook item, None when absent; raise when the read fails."""
    return _get_item(build_dynamodb_adapter(), id)


def lookup_webhooks(field: str, value: str) -> list[dict[str, Any]]:
    """Lookup webhooks by a string field value; raise when the scan fails."""
    adapter = build_dynamodb_adapter()
    try:
        result = adapter.scan(
            TableName=table,
            FilterExpression=f"{field} = :{field}",
            ExpressionAttributeValues={f":{field}": {"S": value}},
        )
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_lookup_failed", field=field, **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
    if not result.is_success:
        logger.error("webhook_lookup_failed", field=field, **_failure_fields(result))
        raise _unavailable(result)
    return result.data or []


def _increment_counter(id: str, attribute: str, failure_event: str) -> None:
    """Increment one counter attribute; every SDK failure is logged and dropped.

    A counter must never block webhook delivery, so a ClientError the adapter does
    not classify (e.g. ValidationException) is swallowed too; programmer errors
    still propagate. The increment is not replay-safe, so it is sent without SDK
    retries, and ``if_not_exists`` seeds a missing counter at zero in the same write.
    """
    adapter = build_dynamodb_adapter()
    try:
        result = adapter.update_item(
            retries=False,
            TableName=table,
            Key={"id": {"S": id}},
            UpdateExpression=f"SET {attribute} = if_not_exists({attribute}, :zero) + :inc",
            ExpressionAttributeValues={":inc": {"N": "1"}, ":zero": {"N": "0"}},
        )
    except ClientError as exc:
        logger.error(failure_event, webhook_id=id, **_unclassified_fields(exc))
        return
    if not result.is_success:
        logger.error(failure_event, webhook_id=id, **_failure_fields(result))


def increment_acknowledged_count(id: str) -> None:
    """Increment the acknowledged counter; a failure is logged and dropped."""
    _increment_counter(id, "acknowledged_count", "webhook_acknowledged_count_increment_failed")


def increment_invocation_count(id: str) -> None:
    """Increment the invocation counter; a failure is logged and dropped."""
    _increment_counter(id, "invocation_count", "webhook_invocation_count_increment_failed")


def list_all_webhooks() -> list[dict[str, Any]]:
    """Return every webhook item; raise when the scan fails."""
    adapter = build_dynamodb_adapter()
    try:
        result = adapter.scan(TableName=table, Select="ALL_ATTRIBUTES")
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_list_failed", **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
    if not result.is_success:
        logger.error("webhook_list_failed", **_failure_fields(result))
        raise _unavailable(result)
    return result.data or []


def toggle_webhook(id: str) -> None:
    """Invert the webhook's active flag; skip a missing webhook, raise when a call fails."""
    adapter = build_dynamodb_adapter()
    webhook = _get_item(adapter, id)
    if webhook is None:
        logger.warning("webhook_toggle_not_found", webhook_id=id)
        return
    try:
        result = adapter.update_item(
            TableName=table,
            Key={"id": {"S": id}},
            UpdateExpression="SET active = :active",
            ExpressionAttributeValues={":active": {"BOOL": not webhook["active"]["BOOL"]}},
        )
    except ClientError as exc:
        fields = _unclassified_fields(exc)
        logger.error("webhook_toggle_failed", webhook_id=id, **fields)
        raise WebhookStoreUnavailableError(OperationStatus.PERMANENT_ERROR, error_code=fields["error_code"]) from exc
    if not result.is_success:
        logger.error("webhook_toggle_failed", webhook_id=id, **_failure_fields(result))
        raise _unavailable(result)


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

    known_models: list[type[BaseModel]] = [
        AwsSnsPayload,
        AccessRequest,
        SimpleTextPayload,
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
