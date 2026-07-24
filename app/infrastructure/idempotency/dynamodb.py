"""DynamoDB idempotency cache implementation."""

import json
import time
from typing import Any

import structlog

from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.idempotency.protocol import (
    ClaimOutcome,
    ClaimResult,
    IdempotencyStore,
)
from infrastructure.idempotency.settings import IdempotencySettings
from integrations.aws.dynamodb_next import delete_item, get_item, put_item, scan

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


class DynamoDBCache(IdempotencyCache):
    """DynamoDB-backed idempotency cache.

    Uses dedicated sre_bot_idempotency table with:
    - PK: idempotency_key (string)
    - Attributes: response_json, ttl (for DynamoDB TTL), created_at, operation_type

    Suitable for multi-instance deployments where cache must be shared across all ECS tasks.
    """

    def __init__(
        self,
        idempotency_settings: IdempotencySettings,
        table_name: str = IDEMPOTENCY_TABLE,
    ):
        """Initialize DynamoDB cache.

        Args:
            idempotency_settings: Narrow idempotency settings slice.
            table_name: DynamoDB table name (default: sre_bot_idempotency).
        """
        self.table_name = table_name
        self.ttl_seconds = idempotency_settings.IDEMPOTENCY_TTL_SECONDS
        self.log = logger.bind(table_name=table_name)
        self.log.bind(ttl_seconds=self.ttl_seconds).info("initialized_dynamodb_idempotency_cache")

    def get(self, key: str) -> dict[str, Any] | None:
        """Get cached response for idempotency key.

        Args:
            key: Idempotency key.

        Returns:
            Cached response dict or None if not found/expired.
        """
        log = self.log.bind(key=key)
        try:
            result = get_item(
                table_name=self.table_name,
                Key={PARTITION_KEY: {"S": key}},
            )

            if not result.is_success:
                log.debug("idempotency_cache_get_failed", error=result.message)
                return None

            # DynamoDB get_item returns None data if item not found
            if result.data is None or "Item" not in result.data:
                log.debug("idempotency_cache_miss")
                return None

            item = result.data.get("Item", {})
            response_json_attr = item.get("response_json", {})

            # DynamoDB stores strings in {"S": "value"} format
            if isinstance(response_json_attr, dict) and "S" in response_json_attr:
                response_json_str = response_json_attr["S"]
            else:
                response_json_str = response_json_attr

            cached_response = json.loads(response_json_str)
            if not isinstance(cached_response, dict):
                log.warning("idempotency_cache_invalid_payload_type")
                return None
            log.debug("idempotency_cache_hit")
            return cached_response

        except Exception as e:
            log.exception("idempotency_cache_get_error", error=str(e))
            return None

    def set(self, key: str, response: dict[str, Any], ttl_seconds: int | None = None) -> None:
        """Cache a response for the given idempotency key.

        Args:
            key: Idempotency key.
            response: Response dict to cache.
            ttl_seconds: Time-to-live in seconds (uses config default if None).
        """
        if ttl_seconds is None:
            ttl_seconds = self.ttl_seconds

        log = self.log.bind(key=key, ttl_seconds=ttl_seconds)

        try:
            now = int(time.time())
            ttl_timestamp = now + ttl_seconds

            # Serialize response to JSON
            response_json = json.dumps(response)

            result = put_item(
                table_name=self.table_name,
                Item={
                    PARTITION_KEY: {"S": key},
                    "response_json": {"S": response_json},
                    "ttl": {"N": str(ttl_timestamp)},
                    "created_at": {"N": str(now)},
                    "operation_type": {"S": "api_response"},
                },
            )

            if result.is_success:
                log.debug("idempotency_cache_set_success")
            else:
                log.error("idempotency_cache_set_failed", error=result.message)

        except (TypeError, ValueError) as e:
            log.error("idempotency_cache_serialization_error", error=str(e))
        except Exception as e:
            log.exception("idempotency_cache_set_error", error=str(e))

    def clear(self) -> None:
        """Clear all cached entries.

        Note: This method scans the entire table and deletes all items.
        For production, use DynamoDB TTL or manual cleanup in AWS console.
        Should only be used in testing.
        """
        log = self.log.bind(backend="dynamodb")
        log.warning("idempotency_cache_clear_called")
        try:
            # Scan for all items
            result = scan(table_name=self.table_name)

            if not result.is_success:
                log.error("idempotency_cache_clear_scan_failed", error=result.message)
                return

            items = result.data.get("Items", []) if result.data else []

            # Delete each item
            for item in items:
                key_value = item.get(PARTITION_KEY, {}).get("S")
                if key_value:
                    delete_item(
                        table_name=self.table_name,
                        Key={PARTITION_KEY: {"S": key_value}},
                    )

            log.info("idempotency_cache_cleared", items_deleted=len(items))

        except Exception as e:
            log.exception("idempotency_cache_clear_error", error=str(e))

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with DynamoDB backend information.
        """
        return {
            "backend": "dynamodb",
            "table_name": self.table_name,
            "ttl_seconds": self.ttl_seconds,
            "partition_key": PARTITION_KEY,
        }
