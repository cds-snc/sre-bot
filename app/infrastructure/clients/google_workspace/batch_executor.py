"""Batch execution utilities for Google Workspace API operations."""

import time
from typing import Any, Callable, Optional

import structlog
from googleapiclient.discovery import Resource

from infrastructure.operations.result import OperationResult, OperationStatus

logger = structlog.get_logger()


def execute_batch_request(
    service: Resource,
    requests: list[tuple[str, Any]],
    callback_fn: Optional[Callable] = None,
) -> OperationResult:
    """Execute multiple Google API calls in a single batch request.

    Args:
        service: Authenticated Google service resource
        requests: List of (request_id, api_request) tuples
        callback_fn: Optional callback for batch results

    Returns:
        OperationResult with data containing:
            - results: Dict mapping request_id to response data
            - errors: Dict mapping request_id to error info (if any)
            - summary: Dict with batch execution statistics
    """
    results: dict[str, Any] = {}
    errors: dict[str, dict[str, Any]] = {}

    def enhanced_callback(request_id: str, response: Any, exception: Exception) -> None:
        if exception:
            error_message = str(exception)
            error_code = getattr(exception, "code", "BATCH_ITEM_ERROR")
            errors[request_id] = {
                "message": error_message,
                "error_code": error_code,
                "timestamp": time.time(),
            }
            logger.warning(
                "batch_request_item_failed",
                request_id=request_id,
                error=error_message,
            )
        else:
            if isinstance(response, OperationResult):
                if response.is_success:
                    results[request_id] = response.data
                else:
                    errors[request_id] = {
                        "message": response.message,
                        "error_code": response.error_code,
                    }
            else:
                results[request_id] = response

    callback = callback_fn or enhanced_callback
    batch = service.new_batch_http_request(callback=callback)

    for request_id, api_request in requests:
        batch.add(api_request, request_id=request_id)

    try:
        batch.execute()
    except Exception as e:
        logger.error("batch_execution_failed", error=str(e))
        return OperationResult.permanent_error(
            message=f"Batch execution failed: {str(e)}",
            error_code="BATCH_EXECUTION_ERROR",
        )

    total_requests = len(requests)
    successful_requests = len(results)
    failed_requests = len(errors)

    logger.info(
        "batch_request_completed",
        total=total_requests,
        successful=successful_requests,
        failed=failed_requests,
        success_rate=successful_requests / total_requests if total_requests > 0 else 0,
    )

    data = {
        "results": results,
        "errors": errors,
        "summary": {
            "total": total_requests,
            "successful": successful_requests,
            "failed": failed_requests,
            "success_rate": (
                successful_requests / total_requests if total_requests > 0 else 0
            ),
        },
    }

    if errors:
        return OperationResult.error(
            status=OperationStatus.PERMANENT_ERROR,
            message="Batch request completed with errors",
            error_code="BATCH_ERRORS",
            data=data,
        )
    else:
        return OperationResult.success(
            data=data,
            message="Batch request completed successfully",
        )
