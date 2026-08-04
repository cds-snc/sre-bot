"""DynamoDB idempotency store implementation."""

import json
import time
from typing import Any

import structlog

from infrastructure.idempotency.protocol import (
    ClaimOutcome,
    ClaimResult,
    IdempotencyStore,
)
from infrastructure.idempotency.settings import IdempotencySettings
from integrations.aws.dynamodb_next import delete_item, get_item, put_item

logger = structlog.get_logger().bind(component="idempotency.dynamodb")

# DynamoDB table configuration
IDEMPOTENCY_TABLE = "sre_bot_idempotency"
PARTITION_KEY = "idempotency_key"


class DynamoDBIdempotencyStore(IdempotencyStore):
    """DynamoDB-backed atomic idempotency claim/complete/release primitive."""

    def __init__(
        self,
        idempotency_settings: IdempotencySettings,
        table_name: str = IDEMPOTENCY_TABLE,
    ) -> None:
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

        claim_result = put_item(
            table_name=self.table_name,
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

        if claim_result.is_success:
            return ClaimOutcome(result=ClaimResult.NEW)

        if claim_result.error_code != "ConditionalCheckFailedException":
            raise RuntimeError(f"Failed to claim idempotency key: {claim_result.message}")

        read_result = get_item(
            table_name=self.table_name,
            Key={PARTITION_KEY: {"S": key}},
            ConsistentRead=True,
        )

        if not read_result.is_success or read_result.data is None or "Item" not in read_result.data:
            return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

        item = read_result.data.get("Item", {})
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

        result = put_item(
            table_name=self.table_name,
            Item={
                PARTITION_KEY: {"S": key},
                "status": {"S": ClaimResult.COMPLETED.name},
                "outcome_json": {"S": outcome_json},
                "completed_at": {"N": str(now)},
                "ttl": {"N": str(ttl_timestamp)},
            },
        )

        if not result.is_success:
            raise RuntimeError(f"Failed to complete idempotency key: {result.message}")

    def release(self, key: str) -> None:
        """Delete key so failed processing can be retried via redelivery."""
        result = delete_item(
            table_name=self.table_name,
            Key={PARTITION_KEY: {"S": key}},
        )
        if not result.is_success:
            raise RuntimeError(f"Failed to release idempotency key: {result.message}")
