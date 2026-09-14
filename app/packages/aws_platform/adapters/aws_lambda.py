"""AWS Lambda adapter.

Holds a typed boto3 lambda client built by ``get_aws_client``, calls the SDK
directly (pagination through ``get_paginator``), classifies expected SDK
errors with ``classify_aws_error`` and returns ``OperationResult`` at every
operation. Programmer errors propagate.

Named ``aws_lambda`` rather than ``lambda`` because ``lambda`` is a Python
keyword. The client is built in-account (no ``SERVICE_ROLE_MAP`` entry), so
callers build the adapter with :func:`build_lambda_adapter` at function entry,
never at import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_lambda.client import LambdaClient

logger = structlog.get_logger()

type _PaginatorName = Literal["list_functions", "list_layers"]


class LambdaAdapter:
    """Lambda operations returning ``OperationResult``.

    Args:
        client: lambda client; every operation is a read.
    """

    def __init__(self, client: LambdaClient) -> None:
        self._client = client

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_lambda_operation_failed",
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

    def _paginate(
        self, paginator_name: _PaginatorName, response_key: str, **kwargs: Any
    ) -> OperationResult[list[dict[str, Any]]]:
        """Flatten every page of a paginated operation into one list."""

        def collect() -> list[dict[str, Any]]:
            paginator = self._client.get_paginator(paginator_name)
            items: list[dict[str, Any]] = []
            for page in paginator.paginate(**kwargs):
                page_items = page.get(response_key, [])
                if isinstance(page_items, list):
                    items.extend(page_items)
            return items

        return self._call(paginator_name, collect)

    # -- functions ------------------------------------------------------------

    def list_functions(self) -> OperationResult[list[dict[str, Any]]]:
        """List every Lambda function across all pages."""
        return self._paginate("list_functions", "Functions")

    def list_layers(self) -> OperationResult[list[dict[str, Any]]]:
        """List every Lambda layer across all pages."""
        return self._paginate("list_layers", "Layers")


def build_lambda_adapter() -> LambdaAdapter:
    """Build the adapter in-account; ``lambda`` has no ``SERVICE_ROLE_MAP`` entry."""
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("lambda") or None
    return LambdaAdapter(get_aws_client("lambda", role_arn=role_arn))
