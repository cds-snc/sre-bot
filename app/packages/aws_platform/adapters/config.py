"""AWS Config adapter.

Holds a typed boto3 config client built by ``get_aws_client``, calls the SDK
directly (pagination through ``get_paginator``), classifies expected SDK
errors with ``classify_aws_error`` and returns ``OperationResult`` at every
operation. Programmer errors propagate.

The client carries eagerly assumed STS credentials, so callers build the
adapter with :func:`build_config_adapter` at function entry, never at import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_config.client import ConfigServiceClient

logger = structlog.get_logger()

type _PaginatorName = Literal["describe_aggregate_compliance_by_config_rules"]


class ConfigAdapter:
    """Config operations returning ``OperationResult``.

    Args:
        client: config client; every operation is a read.
    """

    def __init__(self, client: ConfigServiceClient) -> None:
        self._client = client

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_config_operation_failed",
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

    # -- compliance -----------------------------------------------------------

    def describe_aggregate_compliance_by_config_rules(
        self, config_aggregator_name: str, filters: dict[str, Any] | None = None
    ) -> OperationResult[list[dict[str, Any]]]:
        """List every aggregate compliance result for a configuration aggregator across all pages.

        Filters is omitted from the request when not given: passing ``Filters=None``
        explicitly raises a botocore ParamValidationError.
        """
        kwargs: dict[str, Any] = {"ConfigurationAggregatorName": config_aggregator_name}
        if filters:
            kwargs["Filters"] = filters
        return self._paginate("describe_aggregate_compliance_by_config_rules", "AggregateComplianceByConfigRules", **kwargs)


def build_config_adapter() -> ConfigAdapter:
    """Build the adapter with the config role from ``SERVICE_ROLE_MAP``."""
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("config") or None
    return ConfigAdapter(get_aws_client("config", role_arn=role_arn))
