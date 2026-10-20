"""Generic DynamoDB record store for DynamoDB-backed feature repositories.

Provides a clean interface over a typed boto3 DynamoDB client from
``integrations.aws.client.get_aws_client`` with automatic Python ↔ DynamoDB
type conversion via boto3's built-in ``TypeSerializer`` / ``TypeDeserializer``.

Feature packages MUST NOT call boto3 clients directly. Instead, define a thin
repository class that takes ``contracts.records.RecordStore``
as a constructor argument, declares its ``RecordTable`` once, and delegates
all DynamoDB I/O here.
"""

from collections.abc import Mapping, Sequence
from functools import cache
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import structlog
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError

from contracts.operations.result import OperationResult
from contracts.operations.status import OperationStatus
from contracts.records import (
    READ_LIMIT_EXCEEDED,
    ExpectedValue,
    IncrementAttribute,
    KeySchema,
    RecordChange,
    RecordQuery,
    RecordStore,
    RecordTable,
    RemoveAttribute,
    SetAttribute,
    SortCondition,
    SortOperator,
    SortOrder,
    resolve_query_key,
    validate_read_limit,
    validate_record_item,
    validate_record_update,
)
from integrations.aws.client import classify_aws_error, get_aws_client

if TYPE_CHECKING:
    from types_boto3_dynamodb.client import DynamoDBClient

logger = structlog.get_logger(__name__)

_serializer = TypeSerializer()
_deserializer = TypeDeserializer()

# Per-call owner of a put_if_not_exists write (decisions/reliability.md); never returned by a read.
_WRITER_ATTRIBUTE = "_rs_write_token"


def _new_write_token() -> str:
    """Return an opaque token for one put_if_not_exists call."""
    return uuid4().hex


def _stored_writer(exc: ClientError) -> str | None:
    """Return the write token of the item a failed condition returned (``ALL_OLD``), if any."""
    # ClientError's typed response does not declare the modeled Item member.
    response = cast(Mapping[str, Any], exc.response)
    writer = (response.get("Item") or {}).get(_WRITER_ATTRIBUTE) or {}
    return writer.get("S")


def _item_key(table: RecordTable, item: Mapping[str, Any]) -> dict[str, Any]:
    """Return the item's key attributes, for log context; never the payload."""
    attributes = [table.key.partition] if table.key.sort is None else [table.key.partition, table.key.sort]
    return {attribute: item.get(attribute) for attribute in attributes}


def _serialize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Serialize a plain Python dict to DynamoDB attribute format.

    Skips None values — DynamoDB does not accept null attribute values in
    put_item or as key conditions.
    """
    return {k: _serializer.serialize(v) for k, v in item.items() if v is not None}


def _deserialize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Deserialize a DynamoDB attribute dict to a plain Python dict.

    Numeric values are returned as ``Decimal`` by the boto3 deserializer.
    Callers that expect ``int``/``float`` should cast as needed. The write
    token is the store's own and is dropped.
    """
    return {k: _deserializer.deserialize(v) for k, v in item.items() if k != _WRITER_ATTRIBUTE}


def _key_condition(key: KeySchema, spec: RecordQuery) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Build the key condition, attribute names and serialized values for a query."""
    names = {"#pk": key.partition}
    values: dict[str, Any] = {":pk": _serializer.serialize(spec.partition)}
    expression = "#pk = :pk"
    if spec.sort is not None and key.sort is not None:
        names["#sk"] = key.sort
        values[":sk"] = _serializer.serialize(spec.sort.value)
        expression += f" AND {_sort_expression(spec.sort)}"
    return expression, names, values


def _sort_expression(condition: SortCondition) -> str:
    match condition.operator:
        case SortOperator.EQ:
            return "#sk = :sk"
        case SortOperator.LT:
            return "#sk < :sk"
        case SortOperator.BEGINS_WITH:
            return "begins_with(#sk, :sk)"


def _update_request(
    table: RecordTable,
    changes: Sequence[RecordChange],
    expected: Mapping[str, ExpectedValue] | None,
) -> dict[str, Any]:
    """Build one UpdateItem expression set: SET and REMOVE clauses plus the existence and guard condition.

    Every attribute name goes through a placeholder, so reserved words and
    special characters never reach the expression.
    """
    names = {"#pk": table.key.partition}
    values: dict[str, Any] = {}
    set_clauses: list[str] = []
    remove_clauses: list[str] = []
    for index, change in enumerate(changes):
        name = f"#c{index}"
        names[name] = change.attribute
        match change:
            case SetAttribute(value=value):
                values[f":v{index}"] = _serializer.serialize(value)
                set_clauses.append(f"{name} = :v{index}")
            case IncrementAttribute(delta=delta):
                values[f":v{index}"] = _serializer.serialize(delta)
                values[":zero"] = _serializer.serialize(0)
                set_clauses.append(f"{name} = if_not_exists({name}, :zero) + :v{index}")
            case RemoveAttribute():
                remove_clauses.append(name)
    conditions = ["attribute_exists(#pk)"]
    for index, (attribute, value) in enumerate((expected or {}).items()):
        name = f"#e{index}"
        names[name] = attribute
        if value is None:
            values[":null"] = _serializer.serialize(None)
            conditions.append(f"(attribute_not_exists({name}) OR {name} = :null)")
        else:
            values[f":e{index}"] = _serializer.serialize(value)
            conditions.append(f"{name} = :e{index}")
    clauses = []
    if set_clauses:
        clauses.append("SET " + ", ".join(set_clauses))
    if remove_clauses:
        clauses.append("REMOVE " + ", ".join(remove_clauses))
    request: dict[str, Any] = {
        "UpdateExpression": " ".join(clauses),
        "ConditionExpression": " AND ".join(conditions),
        "ExpressionAttributeNames": names,
    }
    if values:
        request["ExpressionAttributeValues"] = values
    return request


class DynamoDBRecordStore(RecordStore):
    """Generic DynamoDB record store.

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
        logger.info("initialized_record_store")

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
        table: RecordTable,
        item: dict[str, Any],
    ) -> OperationResult:
        """Write (or overwrite) an item.

        Args:
            table: Table declaration.
            item: Plain Python dict.  Keys must include the table's primary key.

        Returns:
            ``OperationResult[None]`` — success with no data payload, or error.

        Raises:
            ValueError: The item names a reserved attribute.
        """
        validate_record_item(item)
        serialized = _serialize_item(item)
        result: OperationResult[Any]
        try:
            self._dynamodb.put_item(TableName=table.name, Item=serialized)
            result = OperationResult.success(data=None)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if result.is_success:
            logger.debug("records_put_ok", table=table.name)
        else:
            logger.error(
                "records_put_error",
                table=table.name,
                operation="put",
                key=_item_key(table, item),
                error=result.message,
                error_code=result.error_code,
            )
        return result

    def put_if_not_exists(
        self,
        table: RecordTable,
        item: dict[str, Any],
    ) -> OperationResult:
        """Write an item only if no item with the same primary key exists.

        One conditional PutItem makes the write atomic. The item carries a
        fresh write token, and a failed condition returns the stored item
        (``ALL_OLD``): when that item carries this call's token, the SDK
        retried a request whose first attempt landed, so the item was created
        by this call. A replay that meets an item another writer replaced or
        deleted in between cannot be recognised and reports that it existed.

        Args:
            table: Table declaration; its partition attribute drives the
                ``attribute_not_exists`` condition, which DynamoDB evaluates
                against the item with the same full primary key.
            item: Plain Python dict.

        Returns:
            ``OperationResult[bool]``: ``data=True`` when this call created
            the item, ``data=False`` when it already existed, or error.

        Raises:
            ValueError: The item names a reserved attribute.
        """
        validate_record_item(item)
        token = _new_write_token()
        log = logger.bind(table=table.name, operation="put_if_not_exists", key=_item_key(table, item))
        try:
            self._dynamodb.put_item(
                TableName=table.name,
                Item=_serialize_item({**item, _WRITER_ATTRIBUTE: token}),
                ConditionExpression="attribute_not_exists(#pk)",
                ExpressionAttributeNames={"#pk": table.key.partition},
                ReturnValuesOnConditionCheckFailure="ALL_OLD",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                if _stored_writer(exc) == token:
                    log.info("records_put_if_not_exists_replay_resolved")
                    return OperationResult.success(data=True, message="Item created")
                log.debug("records_put_if_not_exists_already_exists")
                return OperationResult.success(data=False, message="Item already exists")
            result: OperationResult[Any] = self._map_sdk_exception(exc)
        except BotoCoreError as exc:
            result = self._map_sdk_exception(exc)
        else:
            log.debug("records_put_if_not_exists_created")
            return OperationResult.success(data=True, message="Item created")
        log.error("records_put_if_not_exists_error", error=result.message, error_code=result.error_code)
        return result

    def delete(
        self,
        table: RecordTable,
        key: dict[str, Any],
    ) -> OperationResult:
        """Delete an item by primary key.

        Args:
            table: Table declaration.
            key: Plain Python dict identifying the item (partition + sort key).

        Returns:
            ``OperationResult[None]``
        """
        serialized_key = _serialize_item(key)
        result: OperationResult[Any]
        try:
            self._dynamodb.delete_item(TableName=table.name, Key=serialized_key)
            result = OperationResult.success(data=None)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if result.is_success:
            logger.debug("records_delete_ok", table=table.name)
        else:
            logger.error(
                "records_delete_error",
                table=table.name,
                error=result.message,
                error_code=result.error_code,
            )
        return result

    def update(
        self,
        table: RecordTable,
        key: dict[str, Any],
        changes: Sequence[RecordChange],
        *,
        expected: Mapping[str, ExpectedValue] | None = None,
    ) -> OperationResult:
        """Apply a change set to an existing item in one conditional UpdateItem.

        ``attribute_exists`` on the partition attribute stops the write from
        creating an item. On a condition failure, ``ALL_OLD`` returns the
        item only when it exists, which tells a missing item from an unmet
        guard without a second read.

        Args:
            table: Table declaration.
            key: Plain Python dict with exactly the table's key attributes.
            changes: Non-empty set, remove and increment changes.
            expected: Optional equality guard on non-key attributes; ``None``
                means the attribute is absent.

        Returns:
            ``OperationResult[dict]`` with the updated item; ``success`` with
            ``data=None`` when the guard does not hold; ``NOT_FOUND`` when
            the item does not exist; or error.

        Raises:
            ValueError: The key, changes or guard break the update rules.
        """
        validate_record_update(table, key, changes, expected)
        try:
            response = self._dynamodb.update_item(
                TableName=table.name,
                Key=_serialize_item(key),
                ReturnValues="ALL_NEW",
                ReturnValuesOnConditionCheckFailure="ALL_OLD",
                **_update_request(table, changes, expected),
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                if "Item" in exc.response:
                    logger.debug("records_update_guard_not_satisfied", table=table.name)
                    return OperationResult.success(data=None, message="Guard not satisfied")
                return OperationResult.error(OperationStatus.NOT_FOUND, message=f"Item not found in {table.name}")
            result: OperationResult[Any] = self._map_sdk_exception(exc)
        except BotoCoreError as exc:
            result = self._map_sdk_exception(exc)
        else:
            logger.debug("records_update_ok", table=table.name)
            return OperationResult.success(data=_deserialize_item(response.get("Attributes", {})))
        logger.error(
            "records_update_error",
            table=table.name,
            error=result.message,
            error_code=result.error_code,
        )
        return result

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get(
        self,
        table: RecordTable,
        key: dict[str, Any],
    ) -> OperationResult:
        """Get a single item by primary key.

        Args:
            table: Table declaration.
            key: Plain Python dict with the item's primary key attributes.

        Returns:
            ``OperationResult[dict]`` with the deserialized item, or
            ``OperationResult.not_found`` if the item does not exist.
        """
        serialized_key = _serialize_item(key)
        try:
            response = self._dynamodb.get_item(TableName=table.name, Key=serialized_key)
            result: OperationResult[Any] = OperationResult.success(data=response)
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if not result.is_success:
            logger.error(
                "records_get_error",
                table=table.name,
                error=result.message,
                error_code=result.error_code,
            )
            return result
        raw_item = result.data.get("Item") if result.data else None
        if raw_item is None:
            return OperationResult.error(
                OperationStatus.NOT_FOUND,
                message=f"Item not found in {table.name}",
            )
        return OperationResult.success(data=_deserialize_item(raw_item))

    def query(
        self,
        table: RecordTable,
        spec: RecordQuery,
    ) -> OperationResult:
        """Query items matching a key condition.

        Follows DynamoDB's continuation keys until every match is read or
        ``spec.limit`` items are collected. An index query returns full items,
        like a table query: the contract's indexes project every attribute.

        Args:
            table: Table declaration; ``spec.index`` resolves through its indexes.
            spec: Partition value, optional sort condition, index, limit and order.

        Returns:
            ``OperationResult[list[dict]]`` with deserialized items, or error.

        Raises:
            ValueError: ``spec`` does not fit the table's declared key layout.
        """
        key = resolve_query_key(table, spec)
        expression, names, values = _key_condition(key, spec)
        query_args: dict[str, Any] = {
            "TableName": table.name,
            "KeyConditionExpression": expression,
            "ExpressionAttributeNames": names,
            "ExpressionAttributeValues": values,
            "ScanIndexForward": spec.order is SortOrder.ASC,
        }
        if spec.index is not None:
            query_args["IndexName"] = table.indexes[spec.index].physical_name
        if spec.limit is not None:
            query_args["PaginationConfig"] = {"MaxItems": spec.limit, "PageSize": spec.limit}
        try:
            paginator = self._dynamodb.get_paginator("query")
            raw_items: list[dict[str, Any]] = []
            for page in paginator.paginate(**query_args):
                page_items = page.get("Items", [])
                if isinstance(page_items, list):
                    raw_items.extend(page_items)
            result = OperationResult.success(data=raw_items[: spec.limit])
        except (ClientError, BotoCoreError) as exc:
            result = self._map_sdk_exception(exc)
        if not result.is_success:
            logger.error(
                "records_query_error",
                table=table.name,
                error=result.message,
                error_code=result.error_code,
            )
            return result
        raw_items = result.data if isinstance(result.data, list) else []
        return OperationResult.success(data=[_deserialize_item(item) for item in raw_items])

    def read_all(
        self,
        table: RecordTable,
        *,
        max_items: int,
    ) -> OperationResult:
        """Read every item of the table with a strongly consistent Scan.

        Follows ``LastEvaluatedKey`` page by page and stops as soon as one
        item more than ``max_items`` has been read, so an oversized table
        costs at most one page past the cap. ``ConsistentRead`` includes every
        write completed before the Scan began, at twice the read cost.

        Args:
            table: Table declaration; the Scan reads the table, never an index.
            max_items: The most items the caller expects the table to hold.

        Returns:
            ``OperationResult[list[dict]]`` with every deserialized item;
            ``PERMANENT_ERROR`` with ``READ_LIMIT_EXCEEDED`` when the table
            holds more than ``max_items``; or a classified SDK error.

        Raises:
            ValueError: ``max_items`` is below 1.
        """
        validate_read_limit(max_items)
        log = logger.bind(table=table.name, operation="read_all", max_items=max_items)
        raw_items: list[dict[str, Any]] = []
        try:
            paginator = self._dynamodb.get_paginator("scan")
            pages = paginator.paginate(
                TableName=table.name,
                ConsistentRead=True,
                PaginationConfig={"MaxItems": max_items + 1},
            )
            for page in pages:
                raw_items.extend(page.get("Items", []))
        except (ClientError, BotoCoreError) as exc:
            result: OperationResult[Any] = self._map_sdk_exception(exc)
            log.error("records_read_all_error", error=result.message, error_code=result.error_code)
            return result
        if len(raw_items) > max_items:
            log.warning("records_read_all_limit_exceeded")
            return OperationResult.error(
                OperationStatus.PERMANENT_ERROR,
                message=f"{table.name} holds more than {max_items} items",
                error_code=READ_LIMIT_EXCEEDED,
            )
        log.debug("records_read_all_ok", count=len(raw_items))
        return OperationResult.success(data=[_deserialize_item(item) for item in raw_items])


@cache
def get_record_store() -> RecordStore:
    """Provider function for the record store.

    Returns:
        RecordStore instance.
    """
    dynamodb = get_aws_client("dynamodb")
    return DynamoDBRecordStore(dynamodb)
