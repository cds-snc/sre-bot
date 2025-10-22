"""
Google Workspace API Integration Utilities

This module provides streamlined, standardized utilities for interacting with Google Workspace APIs.
It features:

- Centralized error handling and retry logic for all Google API calls
- Standardized response modeling via IntegrationResponse objects
- Batch request execution with integrated error and result aggregation
- Simplified pagination for list operations
- Service account authentication with delegated access and custom scopes
- Backward-compatible decorator for legacy error handling

Key Functions:
    - get_google_service(service: str, version: str, scopes: Optional[List[str]], delegated_user_email: Optional[str]) -> googleapiclient.discovery.Resource:
        Returns an authenticated Google service resource using service account credentials.

    - execute_api_call(func_name: str, api_call: Callable, max_retries: Optional[int] = None) -> IntegrationResponse:
        Executes a Google API call with standardized error handling, retry logic, and response modeling.

    - execute_batch_request(service: Resource, requests: List[Tuple], callback_fn: Optional[Callable] = None) -> IntegrationResponse:
        Executes multiple API calls in a single batch request, aggregating results and errors.

    - paginate_all_results(request, resource_key: Optional[str] = None) -> IntegrationResponse:
        Paginates through all results for list operations, returning a standardized response.

    - execute_google_api_call(service_name: str, version: str, resource_path: str, method: str, ...) -> IntegrationResponse:
        Simplifies Google API calls with integrated error handling, pagination, and response modeling.

    - handle_google_api_errors(func: Callable) -> Callable:
        Decorator for backward compatibility, wrapping legacy functions with standardized error handling.
"""

import json
import time

from functools import wraps
from json import JSONDecodeError
from typing import Any, Callable, List, Optional, Tuple, Union, cast

from core.config import settings
from core.logging import get_module_logger
from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

# IntegrationResponse and helpers for standardized response modeling
from models.integrations import (
    IntegrationResponse,
    build_error_info,
    build_success_response,
    build_error_response,
)

# Define the default arguments
GOOGLE_WORKSPACE_CUSTOMER_ID = settings.google_workspace.GOOGLE_WORKSPACE_CUSTOMER_ID
GCP_SRE_SERVICE_ACCOUNT_KEY_FILE = (
    settings.google_workspace.GCP_SRE_SERVICE_ACCOUNT_KEY_FILE
)
SRE_BOT_EMAIL = settings.google_workspace.SRE_BOT_EMAIL

logger = get_module_logger()

# Enhanced error configuration (from enhanced_error_handling.py)
ERROR_CONFIG = {
    "non_critical_errors": {
        "get_user": ["not found", "timed out"],
        "get_member": ["not found", "member not found"],
        "get_group": ["not found", "group not found"],
        "get_sheet": ["unable to parse range"],
    },
    "retry_errors": [429, 500, 502, 503, 504],
    "rate_limit_delay": 60,
    "default_max_retries": 3,
    "default_backoff_factor": 1.0,
}


class GoogleAPIError(Exception):
    """Custom exception for Google API errors with structured data."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        function_name: Optional[str] = None,
        retry_after: Optional[int] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.function_name = function_name
        self.retry_after = retry_after
        super().__init__(message)


def _calculate_retry_delay(attempt: int, status_code: int) -> float:
    """Calculate retry delay based on attempt and error type."""
    if status_code == 429:
        raw = ERROR_CONFIG["rate_limit_delay"]
        numeric = cast(Union[int, float, str], raw)
        try:
            return float(numeric)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"ERROR_CONFIG['rate_limit_delay'] must be numeric or numeric string, got {type(raw)!r}"
            ) from exc
    else:
        raw = ERROR_CONFIG["default_backoff_factor"]
        numeric = cast(Union[int, float, str], raw)
        try:
            return float(numeric) * (2**attempt)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"ERROR_CONFIG['default_backoff_factor'] must be numeric or numeric string, got {type(raw)!r}"
            ) from exc


def _get_retry_codes(error_config) -> Optional[set]:
    """Extract retry codes from error config, handling type errors gracefully."""
    raw_retry_errors = (
        error_config.get("retry_errors") if isinstance(error_config, dict) else None
    )
    if isinstance(raw_retry_errors, (list, tuple, set)):
        try:
            return {int(x) for x in raw_retry_errors}
        except (TypeError, ValueError):
            return None
    return None


def _should_retry(
    auto_retry: bool,
    retry_codes: Optional[set],
    error: HttpError,
    is_last_attempt: bool,
) -> bool:
    """Determine if the API call should be retried based on error and config."""
    return (
        auto_retry
        and retry_codes is not None
        and int(error.resp.status) in retry_codes
        and not is_last_attempt
    )


def _handle_final_error(
    error: Exception,
    function_name: str,
) -> IntegrationResponse:
    """Handle the final error after all retries are exhausted."""
    error_message = str(error).lower()

    # Check if this is a known non-critical error (only via config)
    raw_nc = (
        ERROR_CONFIG.get("non_critical_errors")
        if isinstance(ERROR_CONFIG, dict)
        else None
    )
    is_non_critical_config = False
    if isinstance(raw_nc, dict):
        function_errs = raw_nc.get(function_name)
        if isinstance(function_errs, (list, tuple, set)):
            is_non_critical_config = any(
                isinstance(err, str) and (err in error_message) for err in function_errs
            )

    status_code = (
        getattr(error, "resp", {}).get("status") if hasattr(error, "resp") else None
    )

    if is_non_critical_config:
        logger.warning(
            "google_api_non_critical_error",
            function=function_name,
            error=str(error),
            status_code=status_code,
        )
        return build_error_response(
            error=error,
            function_name=function_name,
            integration_name="google",
        )
    else:
        logger.error(
            "google_api_error_final",
            function=function_name,
            error=str(error),
            status_code=status_code,
        )
        return build_error_response(
            error=error,
            function_name=function_name,
            integration_name="google",
        )


def execute_api_call(
    func_name: str,
    api_call: Callable[[], Any],
    max_retries: Optional[int] = None,
) -> IntegrationResponse:
    """
    Execute a Google API call with standardized error handling, retry logic, and response modeling.

    Args:
        func_name (str): Name of the calling function for logging
        api_call (Callable[[], Any]): The API call to execute
        max_retries (Optional[int]): Override default max retries (default from config)

    Returns:
        IntegrationResponse: Standardized response object with success, data, error, function_name, and integration_name fields.

    Notes:
        - All errors are handled and returned as IntegrationResponse objects.
        - Automatic retry is always enabled for retryable errors (no argument needed).
        - Non-critical errors are only supported via config, not as a function argument.
        - Legacy flags (response_metadata, non_critical, auto_retry, return_none_on_error) are no longer supported.
    """
    max_retry_attempts = (
        max_retries
        if isinstance(max_retries, int)
        else ERROR_CONFIG["default_max_retries"]
    )
    last_exception: Optional[Exception] = None

    retry_codes = _get_retry_codes(ERROR_CONFIG)

    for attempt in range(
        max_retry_attempts
        if isinstance(max_retry_attempts, int)
        else int(max_retry_attempts) + 1
    ):
        try:
            logger.debug(
                "google_api_call_start",
                function=func_name,
                attempt=attempt + 1,
                max_attempts=(
                    max_retry_attempts
                    if isinstance(max_retry_attempts, int)
                    else int(max_retry_attempts)
                )
                + 1,
            )

            result = api_call()

            if attempt > 0:
                logger.info(
                    "google_api_retry_success",
                    function=func_name,
                    attempt=attempt + 1,
                )

            return build_success_response(
                data=result,
                function_name=func_name,
                integration_name="google",
            )

        except HttpError as e:
            last_exception = e
            is_last_attempt = attempt == max_retry_attempts

            if (
                retry_codes is not None
                and int(e.resp.status) in retry_codes
                and not is_last_attempt
            ):
                delay = _calculate_retry_delay(attempt, e.resp.status)
                logger.warning(
                    "google_api_retrying",
                    function=func_name,
                    attempt=attempt + 1,
                    status_code=e.resp.status,
                    delay=delay,
                    error=str(e),
                )
                time.sleep(delay)
                continue

            return _handle_final_error(
                e,
                func_name,
            )

        except Exception as e:  # pylint: disable=broad-except
            last_exception = e
            return _handle_final_error(
                e,
                func_name,
            )

    # If we exit the retry loop without returning, use the last captured exception
    if last_exception is None:
        last_exception = Exception("Unknown error after retries")

    return _handle_final_error(
        last_exception,
        func_name,
    )


def get_google_service(
    service: str,
    version: str,
    scopes: Optional[List[str]] = None,
    delegated_user_email: Optional[str] = None,
) -> Resource:
    """
    Get an authenticated Google service with built-in retry and timeout.

    Args:
        service (str): The Google service to get.
        version (str): The version of the service to get.
        scopes (list): The list of scopes to request.
        delegated_user_email (str): The email address of the user to impersonate.

    Returns:
        Resource: The authenticated Google service resource.
    """
    creds_json = GCP_SRE_SERVICE_ACCOUNT_KEY_FILE

    if not creds_json:
        logger.error("credentials_json_missing")
        raise ValueError("Credentials JSON not set")

    try:
        creds_info = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(creds_info)

        if delegated_user_email:
            creds = creds.with_subject(delegated_user_email)
        elif SRE_BOT_EMAIL:
            creds = creds.with_subject(SRE_BOT_EMAIL)

        if scopes:
            creds = creds.with_scopes(scopes)

    except JSONDecodeError as json_decode_exception:
        logger.error("invalid_credentials_json", error=str(json_decode_exception))
        raise JSONDecodeError(
            msg="Invalid credentials JSON", doc="Credentials JSON", pos=0
        ) from json_decode_exception

    # Build service
    return build(
        service,
        version,
        credentials=creds,
        cache_discovery=False,
        static_discovery=False,
    )


def execute_batch_request(
    service: Resource,
    requests: List[Tuple],
    callback_fn: Optional[Callable] = None,
) -> IntegrationResponse:
    """
    Execute multiple Google API calls in a single batch request with standardized error handling and response modeling.

    Args:
        service (Resource): Authenticated Google service resource
        requests (List[Tuple]): List of (resource, method, params) tuples
        callback_fn (Optional[Callable]): Optional callback for batch results

    Returns:
        IntegrationResponse: Standardized response object with success, data, error, function_name, and integration_name fields.

    Notes:
        - All errors are handled and returned as IntegrationResponse objects.
        - Legacy flags and response dicts are no longer supported.
    """

    results = {}
    errors = {}

    def enhanced_callback(request_id, response, exception):
        if exception:
            error_info = build_error_info(exception, function_name=request_id)
            error_info["timestamp"] = time.time()
            errors[request_id] = error_info
            logger.warning(
                "batch_request_item_failed",
                request_id=request_id,
                error=str(exception),
                status_code=error_info.get("status_code"),
            )
        else:
            # If standardized, extract IntegrationResponse fields
            if isinstance(response, IntegrationResponse):
                if response.success:
                    results[request_id] = response.data
                else:
                    # If error, add to errors dict
                    errors[request_id] = response.error or {"message": "Unknown error"}
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
        raise

    # Summary statistics
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

    # Standardized IntegrationResponse for batch requests
    if errors:
        # If any errors occurred, return as error response
        error_info = {
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
        return build_error_response(
            error=Exception("Batch request completed with errors"),
            function_name="execute_batch_request",
            integration_name="google",
        ).model_copy(update={"data": results, "error": error_info})
    else:
        # All requests succeeded
        data = {
            "results": results,
            "summary": {
                "total": total_requests,
                "successful": successful_requests,
                "failed": failed_requests,
                "success_rate": (
                    successful_requests / total_requests if total_requests > 0 else 0
                ),
            },
        }
        return build_success_response(
            data=data,
            function_name="execute_batch_request",
            integration_name="google",
        )


def paginate_all_results(
    request, resource_key: Optional[str] = None
) -> IntegrationResponse:
    """
    Simplified pagination using built-in Google API client features with standardized error handling and response modeling.

    Args:
        request: The initial API request object.
        resource_key (str): The key in response containing the list (auto-detected if None).

    Returns:
        IntegrationResponse: Standardized response object with success, data, error, function_name, and integration_name fields.

    Example:
        request = service.users().list(customer=customer_id)
        resp = paginate_all_results(request, "users")
        if resp.success:
            all_users = resp.data  # This will be the list of results
        else:
            error_info = resp.error
    """

    def paginate_call():
        all_results = []
        current_request = request

        while current_request is not None:
            response = current_request.execute()

            if response:
                # Auto-detect resource key if not provided (first list found)
                if not resource_key and isinstance(response, dict):
                    for key in response:
                        if isinstance(response[key], list):
                            detected_key = key
                            break
                    else:
                        detected_key = None
                else:
                    detected_key = resource_key

                if (
                    detected_key
                    and isinstance(response, dict)
                    and detected_key in response
                ):
                    all_results.extend(response[detected_key])
                elif isinstance(response, list):
                    all_results.extend(response)

                # Use built-in pagination if available
                current_request = (
                    current_request.execute_next_chunk()[0]
                    if hasattr(current_request, "execute_next_chunk")
                    else None
                )
            else:
                break

        logger.info("pagination_completed", total_results=len(all_results))
        return all_results

    resp = execute_api_call("paginate_all_results", paginate_call)
    if not isinstance(resp, IntegrationResponse):
        resp = build_success_response(
            data=resp,
            function_name="paginate_all_results",
            integration_name="google",
        )
    return resp


def execute_google_api_call(
    service_name: str,
    version: str,
    resource_path: str,
    method: str,
    scopes: Optional[List[str]] = None,
    delegated_user_email: Optional[str] = None,
    **kwargs: Any,
) -> IntegrationResponse:
    """
    Execute a Google API call using the simplified module-level error handling and standardized response model.

    Args:
        service_name (str): Name of the Google service (e.g., "drive")
        version (str): API version (e.g., "v3")
        resource_path (str): Path to the resource (e.g., "files")
        method (str): API method to call (e.g., "list")
        scopes (Optional[List[str]]): OAuth scopes
        delegated_user_email (Optional[str]): Email for delegated access
        single_page (bool): If True, only fetch a single page of results
        **kwargs: Additional parameters for the API call

    Returns:
        IntegrationResponse: Standardized response object with success, data, error, function_name, and integration_name fields.

    Notes:
        - All errors are handled and returned as IntegrationResponse objects.
        - Automatic retry is always enabled for retryable errors.
        - Legacy flags and response dicts are no longer supported.
    """

    def api_call():
        service = get_google_service(
            service_name, version, scopes, delegated_user_email
        )

        # Traverse resource path
        resource_obj = service
        for resource in resource_path.split("."):
            resource_obj = getattr(resource_obj, resource)()

        # Get API method
        api_method = getattr(resource_obj, method)

        # Create request
        request = api_method(**kwargs)

        # Auto-paginate list operations unless single_page is explicitly requested
        should_paginate = method == "list"

        if should_paginate:
            # Use simplified pagination for list operations
            resource_key = resource_path.split(".")[
                -1
            ]  # e.g., "users" from "users" or "members" from "groups.members"
            result = paginate_all_results(request, resource_key)
            if isinstance(result, IntegrationResponse):
                return result.data
            return result
        else:
            # Simple execution for non-list operations or when single_page=True
            return request.execute()

    # Use module-level error handling
    func_name = f"{method}"
    return execute_api_call(
        func_name,
        api_call,
    )


# Backward compatibility - map old decorator name to module-level function
def handle_google_api_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Backward compatibility decorator that points users to the new approach.

    For new code, use module-level functions like get_user(), get_group(), etc.
    or call execute_google_api_call() with non_critical parameter.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> IntegrationResponse:
        func_name = func.__name__

        def api_call():
            return func(*args, **kwargs)

        return execute_api_call(
            func_name,
            api_call,
        )

    return wrapper
