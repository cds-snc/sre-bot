"""DynamoDB idempotency cache implementation."""

import json
import time
from typing import Any, Dict, Optional

import structlog
from infrastructure.idempotency.cache import IdempotencyCache
from infrastructure.services.providers import get_settings
from integrations.aws.dynamodb_next import get_item, put_item, delete_item, scan

logger = structlog.get_logger()
settings = get_settings()

# DynamoDB table configuration
IDEMPOTENCY_TABLE = "sre_bot_idempotency"
PARTITION_KEY = "idempotency_key"


class DynamoDBCache(IdempotencyCache):
    """DynamoDB-backed idempotency cache.

    Uses dedicated sre_bot_idempotency table with:
    - PK: idempotency_key (string)
    - Attributes: response_json, ttl (for DynamoDB TTL), created_at, operation_type

    Suitable for multi-instance deployments where cache must be shared across all ECS tasks.
    """

    def __init__(self, table_name: str = IDEMPOTENCY_TABLE):
        """Initialize DynamoDB cache.

        Args:
            table_name: DynamoDB table name (default: sre_bot_idempotency).
        """
        self.table_name = table_name
        self.ttl_seconds = settings.idempotency.IDEMPOTENCY_TTL_SECONDS
        logger.info(
            "initialized_dynamodb_idempotency_cache",
            table_name=table_name,
            ttl_seconds=self.ttl_seconds,
            region=settings.aws.AWS_REGION,
        )

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached response for idempotency key.

        Args:
            key: Idempotency key.

        Returns:
            Cached response dict or None if not found/expired.
        """
        try:
            result = get_item(
                table_name=self.table_name,
                Key={PARTITION_KEY: {"S": key}},
            )

            if not result.is_success:
                logger.debug(
                    "idempotency_cache_get_failed",
                    key=key,
                    error=result.message,
                )
                return None

            # DynamoDB get_item returns None data if item not found
            if result.data is None or "Item" not in result.data:
                logger.debug("idempotency_cache_miss", key=key)
                return None

            item = result.data.get("Item", {})
            response_json_attr = item.get("response_json", {})

            # DynamoDB stores strings in {"S": "value"} format
            if isinstance(response_json_attr, dict) and "S" in response_json_attr:
                response_json_str = response_json_attr["S"]
            else:
                response_json_str = response_json_attr

            cached_response = json.loads(response_json_str)
            logger.debug("idempotency_cache_hit", key=key)
            return cached_response

        except Exception as e:
            logger.error(
                "idempotency_cache_get_error",
                key=key,
                error=str(e),
                exc_info=True,
            )
            return None

    def set(self, key: str, response: Dict[str, Any], ttl_seconds: int = None) -> None:
        """Cache a response for the given idempotency key.

        Args:
            key: Idempotency key.
            response: Response dict to cache.
            ttl_seconds: Time-to-live in seconds (uses config default if None).
        """
        if ttl_seconds is None:
            ttl_seconds = self.ttl_seconds

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
                logger.debug(
                    "idempotency_cache_set_success",
                    key=key,
                    ttl_seconds=ttl_seconds,
                )
            else:
                logger.error(
                    "idempotency_cache_set_failed",
                    key=key,
                    error=result.message,
                )

        except (TypeError, ValueError) as e:
            logger.error(
                "idempotency_cache_serialization_error",
                key=key,
                error=str(e),
            )
        except Exception as e:
            logger.error(
                "idempotency_cache_set_error",
                key=key,
                error=str(e),
                exc_info=True,
            )

    def clear(self) -> None:
        """Clear all cached entries.

        Note: This method scans the entire table and deletes all items.
        For production, use DynamoDB TTL or manual cleanup in AWS console.
        Should only be used in testing.
        """
        logger.warning("idempotency_cache_clear_called", backend="dynamodb")
        try:
            # Scan for all items
            result = scan(table_name=self.table_name)

            if not result.is_success:
                logger.error(
                    "idempotency_cache_clear_scan_failed",
                    error=result.message,
                )
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

            logger.info("idempotency_cache_cleared", items_deleted=len(items))

        except Exception as e:
            logger.error(
                "idempotency_cache_clear_error",
                error=str(e),
                exc_info=True,
            )

    def get_stats(self) -> Dict[str, Any]:
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
