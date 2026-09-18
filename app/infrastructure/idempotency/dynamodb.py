"""DynamoDB idempotency store implementation."""

import json
import time
import uuid
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
        - NEW when the contended record is this call's own replayed write

        Claim token. Every call stamps a fresh uuid4 hex into the item. When a response is
        lost (a timeout or a 5xx), botocore resends the identical serialized body, so the
        replayed conditional put fails against the record the first attempt already wrote
        and the re-read finds our own claim. A matching token proves the claim is ours, so
        the outcome is NEW rather than an IN_PROGRESS nobody holds and nobody will release.
        The token is written but never matched on by the condition expression; it is only
        read back here, and it stays off the IdempotencyStore Protocol because it defends
        against botocore's retry rather than expressing anything about the coordination
        contract. This matters for leases, where a phantom IN_PROGRESS strands the key
        until its in-progress TTL expires; a dedup caller treats its own replay and a real
        duplicate alike, which is why the Powertools pattern needs no token.

        Fail-closed re-read. A classified failure of the ConsistentRead returns IN_PROGRESS:
        our own put definitively did not land, and an unreadable store is indistinguishable
        from a real contender. An unclassified error is not downgraded - classify_aws_error
        re-raises it, because an unknown fault is not evidence of contention. This downgrade
        is provisional and lease-scoped: decisions/reliability.md treats a Tier-2 lease as a
        duplication optimization over idempotent job bodies, which argues for failing open,
        but those bodies are not duplicate-safe yet (TASK-99). Skipping one periodic run
        stays the safer default until TASK-100 flips the policy.
        """
        now = int(time.time())
        expires_at = now + self.in_progress_ttl_seconds
        claim_token = uuid.uuid4().hex

        try:
            self._dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    PARTITION_KEY: {"S": key},
                    "status": {"S": ClaimResult.IN_PROGRESS.name},
                    "claim_token": {"S": claim_token},
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

        if status == ClaimResult.IN_PROGRESS.name and item.get("claim_token", {}).get("S") == claim_token:
            return ClaimOutcome(result=ClaimResult.NEW)

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
