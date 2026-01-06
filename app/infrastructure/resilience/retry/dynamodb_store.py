"""DynamoDB-backed retry store for multi-instance deployments.

This module provides a production-ready retry store implementation using
AWS DynamoDB for shared state across multiple application instances.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any
import time
import structlog

from infrastructure.resilience.retry.config import RetryConfig
from infrastructure.resilience.retry.models import RetryRecord
from integrations.aws import dynamodb_next

logger = structlog.get_logger()


class DynamoDBRetryStore:
    """DynamoDB-backed retry store for multi-instance deployments.

    This implementation provides:
    - Shared state across multiple ECS tasks/instances
    - Atomic claim operations using conditional writes
    - Efficient time-based queries using GSI
    - Automatic cleanup via DynamoDB TTL
    - Durable storage surviving instance crashes

    Table Schema:
        PK: record_id (String)
        Attributes: operation_type, payload, attempts, last_error, timestamps,
                   claim_worker, claim_expires_at, status, ttl
        GSI: status-next_retry_at-index (status + next_retry_at)

    Args:
        config: Retry configuration (backoff, max attempts, etc.)
        table_name: DynamoDB table name
        ttl_days: Days until records auto-expire (default: 30)
    """

    def __init__(
        self,
        config: RetryConfig,
        table_name: str,
        ttl_days: int = 30,
    ):
        """Initialize DynamoDB retry store."""
        self.config = config
        self.table_name = table_name
        self.ttl_days = ttl_days
        self._record_counter = 0

        logger.info(
            "dynamodb_retry_store_initialized",
            table_name=table_name,
            max_attempts=config.max_attempts,
            batch_size=config.batch_size,
        )

    def save(self, record: RetryRecord) -> str:
        """Save a retry record to DynamoDB.

        Args:
            record: RetryRecord to save

        Returns:
            Assigned record ID

        Raises:
            ClientError: If DynamoDB operation fails
        """
        # Generate ID if not present
        if not record.id:
            self._record_counter += 1
            record.id = f"retry-{int(time.time())}-{self._record_counter}"

        # Initialize timestamps
        now = datetime.now(timezone.utc)
        if not record.created_at:
            record.created_at = now
        if not record.updated_at:
            record.updated_at = now
        if not record.next_retry_at:
            record.next_retry_at = now

        # Calculate TTL (30 days from now)
        ttl_timestamp = int(time.time()) + (self.ttl_days * 24 * 60 * 60)

        # Prepare DynamoDB item
        item = {
            "record_id": record.id,
            "operation_type": record.operation_type,
            "payload": record.payload,
            "attempts": record.attempts,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "next_retry_at": int(record.next_retry_at.timestamp()),
            "status": "ACTIVE",
            "ttl": ttl_timestamp,
        }

        # Add optional fields
        if record.last_error:
            item["last_error"] = {"S": record.last_error}

        # Convert to DynamoDB format
        dynamodb_item = {
            "record_id": {"S": item["record_id"]},
            "operation_type": {"S": item["operation_type"]},
            "payload": {"S": str(item["payload"])},
            "attempts": {"N": str(item["attempts"])},
            "created_at": {"S": item["created_at"]},
            "updated_at": {"S": item["updated_at"]},
            "next_retry_at": {"N": str(item["next_retry_at"])},
            "status": {"S": item["status"]},
            "ttl": {"N": str(item["ttl"])},
        }

        if "last_error" in item:
            dynamodb_item["last_error"] = item["last_error"]

        result = dynamodb_next.put_item(
            table_name=self.table_name,
            Item=dynamodb_item,
        )

        if result.is_success:
            logger.debug(
                "retry_record_saved",
                record_id=record.id,
                operation_type=record.operation_type,
            )
            return record.id
        else:
            logger.error(
                "dynamodb_save_failed",
                record_id=record.id,
                error=result.message,
                error_code=result.error_code,
            )
            raise RuntimeError(f"Failed to save retry record: {result.message}")

    def fetch_due(self, limit: int = 10) -> List[RetryRecord]:
        """Fetch retry records that are due for processing.

        Uses GSI to efficiently query ACTIVE records where next_retry_at <= now
        and claim has expired or doesn't exist.

        Args:
            limit: Maximum number of records to fetch

        Returns:
            List of due retry records (not claimed)
        """
        now = int(time.time())

        result = dynamodb_next.query(
            table_name=self.table_name,
            IndexName="status-next_retry_at-index",
            KeyConditionExpression="#status = :status AND next_retry_at <= :now",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": {"S": "ACTIVE"},
                ":now": {"N": str(now)},
            },
            Limit=limit * 2,  # Query extra to account for filtering
        )

        if not result.is_success:
            logger.error(
                "dynamodb_fetch_due_failed",
                error=result.message,
                error_code=result.error_code,
            )
            return []

        items = result.data.get("Items", []) if result.data else []

        # Filter out claimed records
        due_records = []
        for item in items:
            # Skip if claimed and claim hasn't expired
            claim_expires_attr = item.get("claim_expires_at", {})
            if isinstance(claim_expires_attr, dict) and "N" in claim_expires_attr:
                claim_expires = int(claim_expires_attr["N"])
                if claim_expires > now:
                    continue

            # Convert to RetryRecord
            record = self._item_to_record(item)
            due_records.append(record)

            if len(due_records) >= limit:
                break

        logger.debug(
            "fetched_due_retry_records",
            count=len(due_records),
            total_queried=len(items),
        )
        return due_records

    def claim_record(self, record_id: str, worker_id: str, lease_seconds: int) -> bool:
        """Claim a record for processing using atomic conditional write.

        Args:
            record_id: ID of record to claim
            worker_id: ID of worker claiming the record
            lease_seconds: How long to hold the claim

        Returns:
            True if claim succeeded, False if already claimed
        """
        now = int(time.time())
        expires_at = now + lease_seconds

        result = dynamodb_next.update_item(
            table_name=self.table_name,
            Key={"record_id": {"S": record_id}},
            UpdateExpression="SET claim_worker = :worker, claim_expires_at = :expires",
            ConditionExpression="attribute_not_exists(claim_worker) OR claim_expires_at < :now",
            ExpressionAttributeValues={
                ":worker": {"S": worker_id},
                ":expires": {"N": str(expires_at)},
                ":now": {"N": str(now)},
            },
        )

        if result.is_success:
            logger.debug(
                "retry_record_claimed",
                record_id=record_id,
                worker=worker_id,
                expires_at=expires_at,
            )
            return True
        else:
            # Conditional check failure means already claimed
            if result.error_code == "ConditionalCheckFailedException":
                logger.debug(
                    "retry_claim_failed_already_claimed",
                    record_id=record_id,
                    worker=worker_id,
                )
                return False
            else:
                logger.error(
                    "dynamodb_claim_failed",
                    record_id=record_id,
                    error=result.message,
                    error_code=result.error_code,
                )
                return False

    def mark_success(self, record_id: str) -> None:
        """Mark a record as successfully processed (remove from table).

        Args:
            record_id: ID of record to mark as successful
        """
        result = dynamodb_next.delete_item(
            table_name=self.table_name,
            Key={"record_id": {"S": record_id}},
        )

        if result.is_success:
            logger.debug("retry_record_success", record_id=record_id)
        else:
            logger.error(
                "dynamodb_mark_success_failed",
                record_id=record_id,
                error=result.message,
                error_code=result.error_code,
            )
            raise RuntimeError(f"Failed to mark success: {result.message}")

    def mark_permanent_failure(
        self, record_id: str, last_error: str | None = None
    ) -> None:
        """Mark a record as permanently failed (move to DLQ).

        Args:
            record_id: ID of record to move to DLQ
            last_error: Optional error message
        """
        now = datetime.now(timezone.utc)
        update_expr = "SET #status = :dlq, updated_at = :now, dlq_timestamp = :now"
        expr_values = {
            ":dlq": "DLQ",
            ":now": now.isoformat(),
        }
        expr_names = {"#status": "status"}

        if last_error:
            update_expr += ", last_error = :error"
            expr_values[":error"] = last_error

        # Remove claim if present
        update_expr += " REMOVE claim_worker, claim_expires_at"

        # Convert to DynamoDB format
        dynamodb_expr_values = {}
        for key, value in expr_values.items():
            if isinstance(value, str):
                dynamodb_expr_values[key] = {"S": value}
            else:
                dynamodb_expr_values[key] = {"S": str(value)}

        result = dynamodb_next.update_item(
            table_name=self.table_name,
            Key={"record_id": {"S": record_id}},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=dynamodb_expr_values,
        )

        if result.is_success:
            logger.info(
                "retry_record_moved_to_dlq",
                record_id=record_id,
                last_error=last_error,
            )
        else:
            logger.error(
                "dynamodb_mark_permanent_failure_failed",
                record_id=record_id,
                error=result.message,
                error_code=result.error_code,
            )
            raise RuntimeError(f"Failed to mark permanent failure: {result.message}")

    def increment_attempt(self, record_id: str, last_error: str | None = None) -> None:
        """Increment attempt counter and reschedule for retry.

        Args:
            record_id: ID of record to increment
            last_error: Optional error message from failed attempt
        """
        # First, get current record to check attempts
        get_result = dynamodb_next.get_item(
            table_name=self.table_name,
            Key={"record_id": {"S": record_id}},
        )

        if (
            not get_result.is_success
            or not get_result.data
            or "Item" not in get_result.data
        ):
            logger.warning(
                "retry_record_not_found_for_increment",
                record_id=record_id,
                error=(
                    get_result.message
                    if not get_result.is_success
                    else "Item not found"
                ),
            )
            return

        item = get_result.data["Item"]
        current_attempts_attr = item.get("attempts", {})
        current_attempts = (
            int(current_attempts_attr.get("N", 0))
            if isinstance(current_attempts_attr, dict)
            else 0
        )
        new_attempts = current_attempts + 1

        # Check if max attempts reached
        if new_attempts >= self.config.max_attempts:
            logger.info(
                "retry_max_attempts_reached",
                record_id=record_id,
                attempts=new_attempts,
            )
            self.mark_permanent_failure(record_id, last_error)
            return

        # Calculate next retry time with exponential backoff
        delay_seconds = self._calculate_retry_delay(current_attempts)
        next_retry_at = int(time.time()) + delay_seconds
        now = datetime.now(timezone.utc)

        # Update record
        update_expr = (
            "SET attempts = :attempts, updated_at = :now, next_retry_at = :next_retry"
        )
        update_expr += " REMOVE claim_worker, claim_expires_at"  # Release claim
        expr_values = {
            ":attempts": {"N": str(new_attempts)},
            ":now": {"S": now.isoformat()},
            ":next_retry": {"N": str(next_retry_at)},
        }

        if last_error:
            update_expr += ", last_error = :error"
            expr_values[":error"] = {"S": last_error}

        result = dynamodb_next.update_item(
            table_name=self.table_name,
            Key={"record_id": {"S": record_id}},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )

        if result.is_success:
            logger.info(
                "retry_attempt_incremented",
                record_id=record_id,
                attempts=new_attempts,
                next_retry_seconds=delay_seconds,
            )
        else:
            logger.error(
                "dynamodb_increment_attempt_failed",
                record_id=record_id,
                error=result.message,
                error_code=result.error_code,
            )
            raise RuntimeError(f"Failed to increment attempt: {result.message}")

    def get_stats(self) -> Dict[str, int]:
        """Get current retry queue statistics.

        Returns:
            Dictionary with active_records, claimed_records, dlq_records counts
        """
        # Count ACTIVE records
        active_result = dynamodb_next.query(
            table_name=self.table_name,
            IndexName="status-next_retry_at-index",
            KeyConditionExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": {"S": "ACTIVE"}},
            Select="COUNT",
        )
        active_count = 0
        if active_result.is_success and active_result.data:
            active_count = active_result.data.get("Count", 0)

        # Count DLQ records
        dlq_result = dynamodb_next.query(
            table_name=self.table_name,
            IndexName="status-next_retry_at-index",
            KeyConditionExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": {"S": "DLQ"}},
            Select="COUNT",
        )
        dlq_count = 0
        if dlq_result.is_success and dlq_result.data:
            dlq_count = dlq_result.data.get("Count", 0)

        # Count claimed records (approximate - would need scan)
        # For performance, we'll skip this in DynamoDB implementation
        claimed_count = 0

        if not active_result.is_success or not dlq_result.is_success:
            logger.error(
                "dynamodb_get_stats_failed",
                active_error=(
                    active_result.message if not active_result.is_success else None
                ),
                dlq_error=dlq_result.message if not dlq_result.is_success else None,
            )

        return {
            "active_records": active_count,
            "claimed_records": claimed_count,  # Not calculated in DynamoDB
            "dlq_records": dlq_count,
        }

    def get_dlq_entries(self, limit: int = 100) -> List[RetryRecord]:
        """Get entries from the dead letter queue.

        Args:
            limit: Maximum number of DLQ entries to return

        Returns:
            List of permanently failed retry records
        """
        result = dynamodb_next.query(
            table_name=self.table_name,
            IndexName="status-next_retry_at-index",
            KeyConditionExpression="#status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": {"S": "DLQ"}},
            Limit=limit,
        )

        if not result.is_success:
            logger.error(
                "dynamodb_get_dlq_entries_failed",
                error=result.message,
                error_code=result.error_code,
            )
            return []

        items = result.data.get("Items", []) if result.data else []
        return [self._item_to_record(item) for item in items]

    def _calculate_retry_delay(self, attempts: int) -> int:
        """Calculate exponential backoff delay.

        Args:
            attempts: Current attempt count

        Returns:
            Delay in seconds
        """
        delay = self.config.base_delay_seconds * (2**attempts)
        return min(delay, self.config.max_delay_seconds)

    def _item_to_record(self, item: Dict[str, Any]) -> RetryRecord:
        """Convert DynamoDB item to RetryRecord.

        Args:
            item: DynamoDB item dictionary (in DynamoDB format with type descriptors)

        Returns:
            RetryRecord instance
        """

        # Helper to extract value from DynamoDB format
        def get_value(attr, default=None):
            if isinstance(attr, dict):
                if "S" in attr:
                    return attr["S"]
                elif "N" in attr:
                    return attr["N"]
            return default

        record_id = get_value(item.get("record_id"))
        operation_type = get_value(item.get("operation_type"))
        payload_str = get_value(item.get("payload"))
        attempts = int(get_value(item.get("attempts", {}), 0))
        last_error = get_value(item.get("last_error"))
        created_at_str = get_value(item.get("created_at"))
        updated_at_str = get_value(item.get("updated_at"))
        next_retry_at_ts = int(get_value(item.get("next_retry_at"), 0))

        # Parse payload (stored as string)
        try:
            import json

            payload = json.loads(payload_str) if payload_str else {}
        except (json.JSONDecodeError, TypeError):
            payload = {}

        return RetryRecord(
            id=record_id,
            operation_type=operation_type,
            payload=payload,
            attempts=attempts,
            last_error=last_error,
            created_at=(
                datetime.fromisoformat(created_at_str)
                if created_at_str
                else datetime.now(timezone.utc)
            ),
            updated_at=(
                datetime.fromisoformat(updated_at_str)
                if updated_at_str
                else datetime.now(timezone.utc)
            ),
            next_retry_at=datetime.fromtimestamp(next_retry_at_ts, tz=timezone.utc),
        )
