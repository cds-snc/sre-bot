"""AWS DynamoDB adapter.

Holds two typed boto3 dynamodb clients built by ``get_aws_client``: a
standard-retry client and a retries-disabled one for writes that are not
replay-safe (``decisions/outbound-clients.md`` item 25). Calls the SDK directly
(scan pagination through ``get_paginator``), classifies expected SDK errors
with ``classify_aws_error`` and returns ``OperationResult`` at every operation.
Programmer errors propagate.

Request and response items keep the low-level ``AttributeValue`` shapes. Only
the operations legacy callers use are exposed; ``query``, ``delete_item`` and
``list_tables`` have no caller and are deliberately not ported.

The clients are built in-account (no ``SERVICE_ROLE_MAP`` entry), so callers
build the adapter with :func:`build_dynamodb_adapter` at function entry, never
at import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Unpack

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_dynamodb.client import DynamoDBClient
    from types_boto3_dynamodb.type_defs import (
        GetItemInputTypeDef,
        PutItemInputTypeDef,
        ScanInputPaginateTypeDef,
        UpdateItemInputTypeDef,
    )

logger = structlog.get_logger()


class DynamoDBAdapter:
    """DynamoDB operations returning ``OperationResult``.

    Args:
        client: dynamodb client with standard retries.
        client_no_retry: dynamodb client with retries disabled, used by
            ``update_item(retries=False)`` for writes that are not replay-safe.
    """

    def __init__(self, client: DynamoDBClient, client_no_retry: DynamoDBClient) -> None:
        self._client = client
        self._client_no_retry = client_no_retry

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_dynamodb_operation_failed",
            operation=operation,
            status=status.value,
            error_code=error_code,
        )
        return OperationResult.error(
            status,
            message=str(exc),
            error_code=error_code,
            retry_after=retry_after,
            provider="aws",
            operation=operation,
        )

    def _call[T](self, operation: str, fn: Callable[[], T]) -> OperationResult[T]:
        """Run one SDK call, classifying ClientError/BotoCoreError; anything else propagates."""
        try:
            return OperationResult.success(data=fn(), provider="aws", operation=operation)
        except (ClientError, BotoCoreError) as exc:
            return self._map_sdk_exception(operation, exc)

    # -- items ----------------------------------------------------------------

    def scan(self, **kwargs: Unpack[ScanInputPaginateTypeDef]) -> OperationResult[list[dict[str, Any]]]:
        """Scan a table, flattening the ``Items`` of every page into one list."""

        def collect() -> list[dict[str, Any]]:
            paginator = self._client.get_paginator("scan")
            items: list[dict[str, Any]] = []
            for page in paginator.paginate(**kwargs):
                page_items = page.get("Items", [])
                if isinstance(page_items, list):
                    items.extend(page_items)
            return items

        return self._call("scan", collect)

    def get_item(self, **kwargs: Unpack[GetItemInputTypeDef]) -> OperationResult[dict[str, Any] | None]:
        """Get one item; an absent item is a success with ``data=None``."""

        def call() -> dict[str, Any] | None:
            item: dict[str, Any] | None = self._client.get_item(**kwargs).get("Item")
            return item

        return self._call("get_item", call)

    def put_item(self, **kwargs: Unpack[PutItemInputTypeDef]) -> OperationResult[None]:
        """Put one item."""

        def call() -> None:
            self._client.put_item(**kwargs)

        return self._call("put_item", call)

    def update_item(self, *, retries: bool = True, **kwargs: Unpack[UpdateItemInputTypeDef]) -> OperationResult[None]:
        """Update one item; ``retries=False`` sends it on the retries-disabled client."""
        client = self._client if retries else self._client_no_retry

        def call() -> None:
            client.update_item(**kwargs)

        return self._call("update_item", call)


def build_dynamodb_adapter() -> DynamoDBAdapter:
    """Build the adapter in-account; ``dynamodb`` has no ``SERVICE_ROLE_MAP`` entry.

    Two clients are built per call: a standard-retry client and a
    retries-disabled one for writes that are not replay-safe.
    """
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("dynamodb") or None
    client = get_aws_client("dynamodb", role_arn=role_arn)
    client_no_retry = get_aws_client("dynamodb", role_arn=role_arn, retries=False)
    return DynamoDBAdapter(client, client_no_retry)
