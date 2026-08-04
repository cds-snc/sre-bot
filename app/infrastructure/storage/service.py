"""Generic storage service for DynamoDB-backed feature repositories.

Provides a clean interface over a typed boto3 DynamoDB client from
``integrations.aws.client.get_aws_client`` with automatic Python ↔ DynamoDB
type conversion via boto3's built-in ``TypeSerializer`` / ``TypeDeserializer``.

Feature packages MUST NOT call boto3 clients directly. Instead, define a thin
repository class that takes ``infrastructure.storage.protocol.StorageService``
as a constructor argument and delegates all DynamoDB I/O here.
"""

from functools import cache
from typing import Any, Protocol, cast

import structlog
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus
from infrastructure.storage.protocol import StorageService
from integrations.aws.client import classify_aws_error, get_aws_client

logger = structlog.get_logger(__name__)

_serializer = TypeSerializer()
_deserializer = TypeDeserializer()


class DynamoDBClient(Protocol):
    def put_item(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_item(self, **kwargs: Any) -> dict[str, Any]: ...

    def delete_item(self, **kwargs: Any) -> dict[str, Any]: ...

    def get_paginator(self, operation_name: str) -> Any: ...


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Serialize a plain Python dict to DynamoDB attribute format.

    Skips None values — DynamoDB does not accept null attribute values in
    put_item or as key conditions.
    """
    return {k: _serializer.serialize(v) for k, v in item.items() if v is not None}


def _deserialize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Deserialize a DynamoDB attribute dict to a plain Python dict.

    Numeric values are returned as ``Decimal`` by the boto3 deserializer.
    Callers that expect ``int``/``float`` should cast as needed.
    """
    return {k: _deserializer.deserialize(v) for k, v in item.items()}


class DynamoDBStorageService:
    """Generic DynamoDB storage service.

    Intended as the single infrastructure-level abstraction over DynamoDB for
    all feature packages.  Handles serialization, deserialization, and error
    normalisation so feature repositories stay free of boto3 plumbing.

    Backed by ``integrations.aws.client.get_aws_client`` and
    ``integrations.aws.client.classify_aws_error`` (see decisions/sdk-typing.md).

    Args:
        dynamodb: Configured boto3 ``DynamoDBClient`` instance (injected by provider).
    """

    def __init__(self, dynamodb: DynamoDBClient) -> None:
        self._dynamodb = dynamodb
        logger.info("initialized_storage_service")

    def _map_sdk_exception(self, exc: Exception) -> OperationResult[Any]:
        status, error_code, retry_after = classify_aws_error(exc)
        return OperationResult.error(
            status=status,
            message=str(exc),
            error_code=error_code,
            retry_after=retry_after,
        )

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def put(
        self,
        table: str,
        item: dict[str, Any],
    ) -> OperationResult:
        """Write (or overwrite) an item.

        Args:
            table: DynamoDB table name.
            item: Plain Python dict.  Keys must include the table's primary key.

        Returns:
            ``OperationResult[None]`` — success with no data payload, or error.
        """
        serialized = _serialize_item(item)
        result: OperationResult[Any]
        try:
            self._dynamodb.put_item(TableName=table, Item=serialized)
            result = OperationResult.success(data=None)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if result.is_success:
            logger.debug("storage_put_ok", table=table)
        else:
            logger.error(
                "storage_put_error",
                table=table,
                error=result.message,
                error_code=result.error_code,
            )
        return result

    def put_if_not_exists(
        self,
        table: str,
        item: dict[str, Any],
        pk_attribute: str,
    ) -> OperationResult:
        """Write an item only if no item with the same primary key exists.

        Uses a DynamoDB ``ConditionExpression`` to make the write atomic.
        Returns ``OperationResult.success(data=True)`` if the item was created,
        ``OperationResult.success(data=False)`` if it already existed.

        Args:
            table: DynamoDB table name.
            item: Plain Python dict.
            pk_attribute: Name of the partition key attribute (used in
                ``attribute_not_exists`` condition).

        Returns:
            ``OperationResult[bool]``
        """
        serialized = _serialize_item(item)
        result: OperationResult[Any]
        try:
            self._dynamodb.put_item(
                TableName=table,
                Item=serialized,
                ConditionExpression=f"attribute_not_exists({pk_attribute})",
            )
            result = OperationResult.success(data=None)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if result.is_success:
            logger.debug("storage_put_if_not_exists_created", table=table)
            return OperationResult.success(data=True, message="Item created")
        if result.error_code == "ConditionalCheckFailedException":
            logger.debug("storage_put_if_not_exists_already_exists", table=table)
            return OperationResult.success(data=False, message="Item already exists")
        logger.error(
            "storage_put_if_not_exists_error",
            table=table,
            error=result.message,
            error_code=result.error_code,
        )
        return result

    def delete(
        self,
        table: str,
        key: dict[str, Any],
    ) -> OperationResult:
        """Delete an item by primary key.

        Args:
            table: DynamoDB table name.
            key: Plain Python dict identifying the item (partition + sort key).

        Returns:
            ``OperationResult[None]``
        """
        serialized_key = _serialize_item(key)
        result: OperationResult[Any]
        try:
            self._dynamodb.delete_item(TableName=table, Key=serialized_key)
            result = OperationResult.success(data=None)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if result.is_success:
            logger.debug("storage_delete_ok", table=table)
        else:
            logger.error(
                "storage_delete_error",
                table=table,
                error=result.message,
                error_code=result.error_code,
            )
        return result

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(
        self,
        table: str,
        key: dict[str, Any],
    ) -> OperationResult:
        """Get a single item by primary key.

        Args:
            table: DynamoDB table name.
            key: Plain Python dict with the item's primary key attributes.

        Returns:
            ``OperationResult[dict]`` with the deserialized item, or
            ``OperationResult.not_found`` if the item does not exist.
        """
        serialized_key = _serialize_item(key)
        try:
            response = self._dynamodb.get_item(TableName=table, Key=serialized_key)
            result: OperationResult[Any] = OperationResult.success(data=response)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if not result.is_success:
            logger.error(
                "storage_get_error",
                table=table,
                error=result.message,
                error_code=result.error_code,
            )
            return result
        raw_item = result.data.get("Item") if result.data else None
        if raw_item is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Item not found in {table}",
            )
        return OperationResult.success(data=_deserialize_item(raw_item))

    def query(
        self,
        table: str,
        key_condition: str,
        expression_values: dict[str, Any],
        **kwargs: Any,
    ) -> OperationResult:
        """Query items using a key condition.

        Automatically paginates and returns all matching items.

        Args:
            table: DynamoDB table name.
            key_condition: DynamoDB ``KeyConditionExpression`` string
                (e.g. ``"pk = :id AND sk > :ts"``).
            expression_values: Placeholder → Python value mapping
                (e.g. ``{":id": "eng@example.com", ":ts": "2026-01-01T00:00:00"}``).
                Values are serialized automatically — do NOT pre-format as
                DynamoDB type dicts.
            **kwargs: Additional DynamoDB query parameters passed through
                verbatim (``IndexName``, ``Limit``, ``ScanIndexForward``,
                ``FilterExpression``, ``ExpressionAttributeNames``, etc.).

        Returns:
            ``OperationResult[list[dict]]`` with deserialized items, or error.
        """
        serialized_values = {k: _serializer.serialize(v) for k, v in expression_values.items()}
        query_args: dict[str, Any] = {
            "TableName": table,
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": serialized_values,
            **kwargs,
        }
        try:
            paginator = self._dynamodb.get_paginator("query")
            raw_items: list[dict[str, Any]] = []
            for page in paginator.paginate(**query_args):
                page_items = page.get("Items", [])
                if isinstance(page_items, list):
                    raw_items.extend(page_items)
            result = OperationResult.success(data=raw_items)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if not result.is_success:
            logger.error(
                "storage_query_error",
                table=table,
                error=result.message,
                error_code=result.error_code,
            )
            return result
        raw_items = result.data if isinstance(result.data, list) else []
        return OperationResult.success(data=[_deserialize_item(item) for item in raw_items])


@cache
def get_storage_service() -> StorageService:
    """Provider function for the storage service.

    Returns:
        StorageService instance.
    """
    dynamodb = cast(DynamoDBClient, get_aws_client("dynamodb"))
    return DynamoDBStorageService(dynamodb)
