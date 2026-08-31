"""DynamoDB idempotency store implementation."""

import json
import time
from typing import TYPE_CHECKING, Any

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.idempotency.protocol import (
    ClaimOutcome,
    ClaimResult,
    IdempotencyStore,
)
from infrastructure.idempotency.settings import IdempotencySettings
from integrations.aws.client import classify_aws_error

if TYPE_CHECKING:
    from types_boto3_dynamodb.client import DynamoDBClient

logger = structlog.get_logger().bind(component="idempotency.dynamodb")

# DynamoDB table configuration
IDEMPOTENCY_TABLE = "sre_bot_idempotency"
PARTITION_KEY = "idempotency_key"


class DynamoDBIdempotencyStore(IdempotencyStore):
    """DynamoDB-backed atomic idempotency claim/complete/release primitive."""

    def __init__(
        self,
        dynamodb: DynamoDBClient,
        idempotency_settings: IdempotencySettings,
        table_name: str = IDEMPOTENCY_TABLE,
    ) -> None:
        self._dynamodb = dynamodb
        self.table_name = table_name
        self.record_ttl_seconds = idempotency_settings.IDEMPOTENCY_TTL_SECONDS
        self.in_progress_ttl_seconds = idempotency_settings.IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS
        self.log = logger.bind(table_name=table_name)

    def claim(self, key: str) -> ClaimOutcome:
        """Atomically claim key with conditional PutItem.

        Behavior:
        - NEW when key does not exist (or stale in-progress claim is expired)
        - COMPLETED when prior completed outcome exists
        - IN_PROGRESS when another worker currently owns the claim
        """
        now = int(time.time())
        expires_at = now + self.in_progress_ttl_seconds

        try:
            self._dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    PARTITION_KEY: {"S": key},
                    "status": {"S": ClaimResult.IN_PROGRESS.name},
                    "claimed_at": {"N": str(now)},
                    "in_progress_expires_at": {"N": str(expires_at)},
                    "ttl": {"N": str(expires_at)},
                },
                ConditionExpression="attribute_not_exists(#pk) OR (#status = :in_progress AND #expires_at < :now)",
                ExpressionAttributeNames={
                    "#pk": PARTITION_KEY,
                    "#status": "status",
                    "#expires_at": "in_progress_expires_at",
                },
                ExpressionAttributeValues={
                    ":in_progress": {"S": ClaimResult.IN_PROGRESS.name},
                    ":now": {"N": str(now)},
                },
            )
            return ClaimOutcome(result=ClaimResult.NEW)
        except (ClientError, BotoCoreError) as exc:
            _, error_code, _ = classify_aws_error(exc)
            if error_code != "ConditionalCheckFailedException":
                raise RuntimeError(f"Failed to claim idempotency key: {exc}") from exc

        try:
            response = self._dynamodb.get_item(
                TableName=self.table_name,
                Key={PARTITION_KEY: {"S": key}},
                ConsistentRead=True,
            )
            item = response.get("Item")
        except (ClientError, BotoCoreError) as exc:
            classified_status, error_code, _ = classify_aws_error(exc)
            self.log.warning(
                "failed_to_read_idempotency_key",
                status=classified_status,
                error_code=error_code,
            )
            return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

        if item is None:
            return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

        status = item.get("status", {}).get("S")

        if status == ClaimResult.COMPLETED.name:
            outcome_json = item.get("outcome_json", {}).get("S")
            if outcome_json is None:
                return ClaimOutcome(result=ClaimResult.COMPLETED, outcome=None)
            return ClaimOutcome(result=ClaimResult.COMPLETED, outcome=json.loads(outcome_json))

        return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

    def complete(self, key: str, outcome: dict[str, Any]) -> None:
        """Write completed outcome for idempotency key."""
        now = int(time.time())
        ttl_timestamp = now + self.record_ttl_seconds
        outcome_json = json.dumps(outcome)

        try:
            self._dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    PARTITION_KEY: {"S": key},
                    "status": {"S": ClaimResult.COMPLETED.name},
                    "outcome_json": {"S": outcome_json},
                    "completed_at": {"N": str(now)},
                    "ttl": {"N": str(ttl_timestamp)},
                },
            )
        except (ClientError, BotoCoreError) as exc:
            classify_aws_error(exc)
            raise RuntimeError(f"Failed to complete idempotency key: {exc}") from exc

    def release(self, key: str) -> None:
        """Delete key so failed processing can be retried via redelivery."""
        try:
            self._dynamodb.delete_item(
                TableName=self.table_name,
                Key={PARTITION_KEY: {"S": key}},
            )
        except (ClientError, BotoCoreError) as exc:
            classify_aws_error(exc)
            raise RuntimeError(f"Failed to release idempotency key: {exc}") from exc
