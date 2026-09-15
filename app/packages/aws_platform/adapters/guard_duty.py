"""AWS GuardDuty adapter.

Holds a typed boto3 guardduty client built by ``get_aws_client``, calls the
SDK directly (pagination through ``get_paginator``), classifies expected SDK
errors with ``classify_aws_error`` and returns ``OperationResult`` at every
operation. Programmer errors propagate.

The client carries eagerly assumed STS credentials, so callers build the adapter
with :func:`build_guard_duty_adapter` at function entry, never at import.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Literal

import structlog
from botocore.exceptions import BotoCoreError, ClientError

from infrastructure.operations import OperationResult
from integrations.aws.client import classify_aws_error, get_aws_client
from integrations.aws.settings import get_aws_settings

if TYPE_CHECKING:
    from types_boto3_guardduty.client import GuardDutyClient

logger = structlog.get_logger()

type _PaginatorName = Literal["list_detectors"]


class GuardDutyAdapter:
    """GuardDuty operations returning ``OperationResult``.

    Args:
        client: guardduty client; every operation is a read.
    """

    def __init__(self, client: GuardDutyClient) -> None:
        self._client = client

    # -- error handling -----------------------------------------------------

    @staticmethod
    def _map_sdk_exception(operation: str, exc: Exception) -> OperationResult[Any]:
        """Classify an expected botocore exception into an error result."""
        status, error_code, retry_after = classify_aws_error(exc)
        logger.warning(
            "aws_guard_duty_operation_failed",
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

    def _paginate(self, paginator_name: _PaginatorName, response_key: str, **kwargs: Any) -> OperationResult[list[Any]]:
        """Flatten every page of a paginated operation into one list."""

        def collect() -> list[Any]:
            paginator = self._client.get_paginator(paginator_name)
            items: list[Any] = []
            for page in paginator.paginate(**kwargs):
                page_items = page.get(response_key, [])
                if isinstance(page_items, list):
                    items.extend(page_items)
            return items

        return self._call(paginator_name, collect)

    # -- detectors ------------------------------------------------------------

    def list_detectors(self) -> OperationResult[list[str]]:
        """List every detector id across all pages."""
        return self._paginate("list_detectors", "DetectorIds")

    # -- findings ---------------------------------------------------------------

    def get_findings_statistics(
        self, detector_id: str, finding_criteria: dict[str, Any] | None = None
    ) -> OperationResult[dict[str, int]]:
        """Return the CountBySeverity statistic for one detector."""

        def get() -> dict[str, int]:
            params: dict[str, Any] = {
                "DetectorId": detector_id,
                "FindingStatisticTypes": ["COUNT_BY_SEVERITY"],
            }
            if finding_criteria is not None:
                params["FindingCriteria"] = finding_criteria
            response = self._client.get_findings_statistics(**params)
            statistics: dict[str, int] = response.get("FindingStatistics", {}).get("CountBySeverity", {})
            return statistics

        return self._call("get_findings_statistics", get)


def build_guard_duty_adapter() -> GuardDutyAdapter:
    """Build the adapter with the guardduty role from ``SERVICE_ROLE_MAP``."""
    role_arn = get_aws_settings().SERVICE_ROLE_MAP.get("guardduty") or None
    return GuardDutyAdapter(get_aws_client("guardduty", role_arn=role_arn))
