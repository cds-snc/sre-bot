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
        The claim condition never matches on the token; this re-read branch is a defence
        against botocore's retry and stays an implementation detail. This matters for leases,
        where a phantom IN_PROGRESS strands the key until its in-progress TTL expires; a dedup
        caller treats its own replay and a real duplicate alike. Separately, every NEW outcome
        returns the token on ClaimOutcome, because complete() and release() are conditional
        on it: that ownership rule is part of the Protocol.

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
            return ClaimOutcome(result=ClaimResult.NEW, claim_token=claim_token)
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
            return ClaimOutcome(result=ClaimResult.NEW, claim_token=claim_token)

        return ClaimOutcome(result=ClaimResult.IN_PROGRESS)

    def complete(self, key: str, outcome: dict[str, Any], claim_token: str) -> bool:
        """Write the completed outcome if claim_token still holds the key.

        The put is conditional on the stored token only, not on the status, and the
        COMPLETED item keeps the token: a botocore replay of a complete whose first attempt
        landed still matches and stays True. A record taken over by another claimant, or
        purged by the TTL sweeper, fails the condition and returns False.
        """
        now = int(time.time())
        ttl_timestamp = now + self.record_ttl_seconds
        outcome_json = json.dumps(outcome)

        try:
            self._dynamodb.put_item(
                TableName=self.table_name,
                Item={
                    PARTITION_KEY: {"S": key},
                    "status": {"S": ClaimResult.COMPLETED.name},
                    "claim_token": {"S": claim_token},
                    "outcome_json": {"S": outcome_json},
                    "completed_at": {"N": str(now)},
                    "ttl": {"N": str(ttl_timestamp)},
                },
                ConditionExpression="#claim_token = :claim_token",
                ExpressionAttributeNames={"#claim_token": "claim_token"},
                ExpressionAttributeValues={":claim_token": {"S": claim_token}},
            )
            return True
        except (ClientError, BotoCoreError) as exc:
            _, error_code, _ = classify_aws_error(exc)
            if error_code == "ConditionalCheckFailedException":
                self.log.warning("claim_ownership_lost", key=key, operation="complete")
                return False
            raise RuntimeError(f"Failed to complete idempotency key: {exc}") from exc

    def release(self, key: str, claim_token: str) -> bool:
        """Delete the key if claim_token still holds it in progress, so redelivery can retry.

        A COMPLETED record is never deleted. A replayed release whose first attempt landed
        finds nothing and returns False; the release still happened.
        """
        try:
            self._dynamodb.delete_item(
                TableName=self.table_name,
                Key={PARTITION_KEY: {"S": key}},
                ConditionExpression="#claim_token = :claim_token AND #status = :in_progress",
                ExpressionAttributeNames={"#claim_token": "claim_token", "#status": "status"},
                ExpressionAttributeValues={
                    ":claim_token": {"S": claim_token},
                    ":in_progress": {"S": ClaimResult.IN_PROGRESS.name},
                },
            )
            return True
        except (ClientError, BotoCoreError) as exc:
            _, error_code, _ = classify_aws_error(exc)
            if error_code == "ConditionalCheckFailedException":
                self.log.warning("claim_ownership_lost", key=key, operation="release")
                return False
            raise RuntimeError(f"Failed to release idempotency key: {exc}") from exc
