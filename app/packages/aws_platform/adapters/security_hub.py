"""AWS Security Hub adapter.

Holds a typed boto3 securityhub client built by ``get_aws_client``, calls the
SDK directly (pagination through ``get_paginator``), classifies expected SDK
errors with ``classify_aws_error`` and returns ``OperationResult`` at every
operation. Programmer errors propagate.

The client carries eagerly assumed STS credentials, so callers build the adapter
with :func:`build_security_hub_adapter` at function entry, never at import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_securityhub.client import SecurityHubClient

logger = structlog.get_logger()

type _PaginatorName = Literal["get_findings"]


class SecurityHubAdapter:
    """Security Hub operations returning ``OperationResult``.

    Args:
        client: securityhub client; every operation is a read.
    """

    def __init__(self, client: SecurityHubClient) -> None:
        self._client = client

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_security_hub_operation_failed",
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
        """Flatten every page of a paginated operation into one list, keyed on response_key.

        Pagination is keyed explicitly (unlike the legacy mirror's unkeyed paginator, which
        flattened every response field, including NextToken, into the result).
        """

        def collect() -> list[dict[str, Any]]:
            paginator = self._client.get_paginator(paginator_name)
            items: list[dict[str, Any]] = []
            for page in paginator.paginate(**kwargs):
                page_items = page.get(response_key, [])
                if isinstance(page_items, list):
                    items.extend(page_items)
            return items

        return self._call(paginator_name, collect)

    # -- findings ---------------------------------------------------------------

    def get_findings(self, filters: dict[str, Any]) -> OperationResult[list[dict[str, Any]]]:
        """List every finding matching filters across all pages, paginated on Findings."""
        return self._paginate("get_findings", "Findings", Filters=filters)


def build_security_hub_adapter() -> SecurityHubAdapter:
    """Build the adapter with the securityhub role from ``SERVICE_ROLE_MAP``."""
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("securityhub") or None
    return SecurityHubAdapter(get_aws_client("securityhub", role_arn=role_arn))
