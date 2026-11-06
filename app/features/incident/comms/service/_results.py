"""Helpers the status-update use cases share."""

from typing import Any

from contracts.operations import OperationResult
from features.incident.core.api import StatusUpdateStage

STAGE_ORDER = tuple(StatusUpdateStage)


def failure[T](result: OperationResult[Any]) -> OperationResult[T]:
    """Carry an error result's classification over to another payload type."""
    return OperationResult.error(
        result.status,
        message=result.message or "status update failed",
        error_code=result.error_code,
        retry_after=result.retry_after,
    )
