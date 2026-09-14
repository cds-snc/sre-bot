"""AWS Cost Explorer adapter.

Holds a typed boto3 cost-explorer client built by ``get_aws_client``, calls
the SDK directly, classifies expected SDK errors with ``classify_aws_error``
and returns ``OperationResult`` at every operation. Programmer errors
propagate.

``get_cost_and_usage`` has no boto3 paginator (confirmed via
``client.can_paginate("get_cost_and_usage") is False``), yet its response can
carry a ``NextPageToken`` when results span more than one page. This adapter
follows that token manually so results are never silently truncated.

The client carries eagerly assumed STS credentials, so callers build the
adapter with :func:`build_cost_explorer_adapter` at function entry, never at
import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_ce.client import CostExplorerClient
    from types_boto3_ce.literals import GranularityType

logger = structlog.get_logger()


class CostExplorerAdapter:
    """Cost Explorer operations returning ``OperationResult``.

    Args:
        client: cost-explorer client; every operation is a read.
    """

    def __init__(self, client: CostExplorerClient) -> None:
        self._client = client

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_cost_explorer_operation_failed",
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

    # -- cost and usage -------------------------------------------------------

    def get_cost_and_usage(
        self,
        time_period: dict[str, str],
        granularity: GranularityType,
        metrics: list[str],
        filter_expression: dict[str, Any] | None = None,
        group_by: list[dict[str, str]] | None = None,
    ) -> OperationResult[list[dict[str, Any]]]:
        """Return the concatenated ``ResultsByTime`` across every page.

        Follows ``NextPageToken`` manually: ``GetCostAndUsage`` has no boto3
        paginator. Filter and GroupBy are only included in the request when
        given, and the same params are repeated on every page (Cost Explorer
        raises ``RequestChangedException`` if params change mid-pagination).
        """
        params: dict[str, Any] = {
            "TimePeriod": time_period,
            "Granularity": granularity,
            "Metrics": metrics,
        }
        if filter_expression:
            params["Filter"] = filter_expression
        if group_by:
            params["GroupBy"] = group_by

        def collect() -> list[dict[str, Any]]:
            results: list[dict[str, Any]] = []
            request = dict(params)
            while True:
                response = self._client.get_cost_and_usage(**request)
                results.extend(dict(item) for item in response.get("ResultsByTime", []))
                next_token = response.get("NextPageToken")
                if not next_token:
                    return results
                request = {**params, "NextPageToken": next_token}

        return self._call("get_cost_and_usage", collect)


def build_cost_explorer_adapter() -> CostExplorerAdapter:
    """Build the adapter with the Cost Explorer role from ``SERVICE_ROLE_MAP``."""
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("ce") or None
    return CostExplorerAdapter(get_aws_client("ce", role_arn=role_arn))
