"""Low-level Google API execution utilities with retry and error handling."""

import time
from typing import Any, Callable, Optional

import structlog
from googleapiclient.errors import HttpError

from infrastructure.operations.result import OperationResult

logger = structlog.get_logger()


# Error configuration
ERROR_CONFIG: dict[str, Any] = {
    "retry_errors": [429, 500, 502, 503, 504],
    "rate_limit_delay": 60,
    "default_max_retries": 3,
    "default_backoff_factor": 1.0,
}


def _calculate_retry_delay(attempt: int, status_code: int) -> float:
    """Calculate retry delay based on attempt and error type.

    Args:
        attempt: Current attempt number (0-indexed)
        status_code: HTTP status code from error response

    Returns:
        Delay in seconds before next retry
    """
    if status_code == 429:
        rate_limit_delay: float = ERROR_CONFIG["rate_limit_delay"]  # type: ignore
        return float(rate_limit_delay)
    else:
        backoff_factor: float = ERROR_CONFIG["default_backoff_factor"]  # type: ignore
        return float(backoff_factor) * (2**attempt)


def execute_google_api_call(
    operation_name: str,
    api_callable: Callable[[], Any],
    max_retries: Optional[int] = None,
) -> OperationResult:
    """Execute a Google API call with retry logic and error handling.

    Args:
        operation_name: Name of operation for logging (e.g., "list_users")
        api_callable: Callable that executes the API call (e.g., request.execute)
        max_retries: Maximum retry attempts (uses default if None)

    Returns:
        OperationResult with standardized status, message, data, error_code

    Example:
        request = service.users().list(customer="my_customer")
        result = execute_google_api_call("list_users", request.execute)
        if result.is_success:
            users = result.data
    """
    max_retries_config: int = ERROR_CONFIG["default_max_retries"]  # type: ignore
    max_attempts = max_retries if max_retries is not None else max_retries_config
    retry_errors_list: list[int] = ERROR_CONFIG["retry_errors"]  # type: ignore
    retry_codes = set(retry_errors_list)

    last_exception: Optional[Exception] = None

    for attempt in range(max_attempts + 1):
        try:
            logger.debug(
                "google_api_call_attempt",
                operation=operation_name,
                attempt=attempt + 1,
                max_attempts=max_attempts + 1,
            )

            result = api_callable()

            if attempt > 0:
                logger.info(
                    "google_api_retry_success",
                    operation=operation_name,
                    attempt=attempt + 1,
                )

            # If api_callable already returns OperationResult, propagate it
            if isinstance(result, OperationResult):
                return result

            return OperationResult.success(
                data=result,
                message=f"{operation_name} succeeded",
            )

        except HttpError as e:
            last_exception = e
            is_last_attempt = attempt == max_attempts
            status_code = int(e.resp.status)

            # Retry logic for retryable errors
            if status_code in retry_codes and not is_last_attempt:
                delay = _calculate_retry_delay(attempt, status_code)
                logger.warning(
                    "google_api_retrying",
                    operation=operation_name,
                    attempt=attempt + 1,
                    status_code=status_code,
                    delay=delay,
                )
                time.sleep(delay)
                continue

            # Non-retryable or last attempt
            logger.error(
                "google_api_error",
                operation=operation_name,
                status_code=status_code,
                error=str(e),
            )

            return OperationResult.permanent_error(
                message=str(e),
                error_code=f"GOOGLE_API_ERROR_{status_code}",
            )

        except Exception as e:
            last_exception = e
            logger.error(
                "google_api_unexpected_error",
                operation=operation_name,
                error=str(e),
            )
            return OperationResult.permanent_error(
                message=str(e),
                error_code="GOOGLE_API_ERROR",
            )

    # Fallback if loop exits without return
    return OperationResult.permanent_error(
        message=str(last_exception) if last_exception else "Unknown error",
        error_code="GOOGLE_API_ERROR",
    )
