"""
Simplified Google Service Module.

This module provides streamlined functions to work with Google Workspace APIs,
leveraging built-in Google API client features and enhanced error handling at the module level.

Functions:
    get_google_service(service: str, version: str) -> googleapiclient.discovery.Resource:
        Returns an authenticated Google service resource.

    execute_api_call(func_name: str, api_call: Callable) -> Any:
        Module-level error handling for all Google API calls.

    execute_batch_request(service: Resource, requests: list) -> dict:
        Execute multiple API calls in a single batch request with enhanced error handling.

    execute_google_api_call(...) -> Any:
        Simplified version using built-in features with integrated error handling.
"""

import json
import time
from functools import wraps
from json import JSONDecodeError
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

from core.config import settings
from core.logging import get_module_logger
from google.oauth2 import service_account
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError

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


def _build_error_info(error: Exception, function_name: str) -> dict:
    """Helper to build error info dict from an exception."""
    status_code = (
        getattr(error, "resp", {}).get("status") if hasattr(error, "resp") else None
    )
    return {
        "message": str(error),
        "status_code": status_code,
        "function_name": function_name,
    }


def _build_response(
    success: bool, data: Any, error_info: Optional[dict], function_name: str
) -> dict:
    """Helper to build standardized response dict."""
    return {
        "success": success,
        "data": data,
        "error": error_info,
        "function_name": function_name,
    }


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


def _handle_final_error(
    error: Exception,
    function_name: str,
    non_critical: bool,
    return_none_on_error: bool,
    response_metadata: bool = False,
) -> Any:
    """Handle the final error after all retries are exhausted."""
    error_message = str(error).lower()

    # Check if this is a known non-critical error
    raw_nc = (
        ERROR_CONFIG.get("non_critical_errors")
        if isinstance(ERROR_CONFIG, dict)
        else None
    )
    is_non_critical_config = False
    if isinstance(raw_nc, dict):
        function_errs = raw_nc.get(function_name)
        if isinstance(function_errs, (list, tuple, set)):
            # Defensive: ensure all elements are strings
            is_non_critical_config = any(
                isinstance(err, str) and (err in error_message) for err in function_errs
            )

    is_non_critical = non_critical or is_non_critical_config

    status_code = (
        getattr(error, "resp", {}).get("status") if hasattr(error, "resp") else None
    )

    if is_non_critical:
        logger.warning(
            "google_api_non_critical_error",
            function=function_name,
            error=str(error),
            status_code=status_code,
        )
        if response_metadata:
            return _build_response(
                False, None, _build_error_info(error, function_name), function_name
            )
        return None
    else:
        logger.error(
            "google_api_error_final",
            function=function_name,
            error=str(error),
            status_code=status_code,
        )
        if return_none_on_error:
            if response_metadata:
                return _build_response(
                    False, None, _build_error_info(error, function_name), function_name
                )
            return None
        raise GoogleAPIError(
            message=str(error), status_code=status_code, function_name=function_name
        ) from error


def execute_api_call(
    func_name: str,
    api_call: Callable[[], Any],
    non_critical: bool = False,
    auto_retry: bool = True,
    max_retries: Optional[int] = None,
    return_none_on_error: bool = False,
    response_metadata: bool = False,
) -> Any:
    """
    Module-level error handling for Google API calls.

    This eliminates the need for decorators by providing centralized error handling.

    Args:
        func_name (str): Name of the calling function for logging
        api_call (callable): The API call to execute
        non_critical (bool): Treat errors as non-critical (log warning, return None)
        auto_retry (bool): Enable automatic retry for retryable errors
        max_retries (int): Override default max retries
        return_none_on_error (bool): Return None instead of raising on errors

    Returns:
        Any: The result of the API call

    Example:
        def my_api_function():
            service = get_google_service("people", "v1")
            request = service.people().get(resourceName="people/me")
            return request.execute()

        result = execute_api_call("my_api_function", my_api_function)
    """
    max_retry_attempts = max_retries or ERROR_CONFIG["default_max_retries"]

    last_exception: Optional[Exception] = None

    for attempt in range(max_retry_attempts + 1):
        try:
            logger.debug(
                "google_api_call_start",
                function=func_name,
                attempt=attempt + 1,
                max_attempts=max_retry_attempts + 1,
            )

            result = api_call()

            if attempt > 0:
                logger.info(
                    "google_api_retry_success",
                    function=func_name,
                    attempt=attempt + 1,
                )

            if response_metadata:
                return _build_response(True, result, None, func_name)
            return result

        except HttpError as e:
            last_exception = e
            is_last_attempt = attempt == max_retry_attempts

            raw_retry_errors = None
            if isinstance(ERROR_CONFIG, dict):
                raw_retry_errors = ERROR_CONFIG.get("retry_errors")

            retry_codes = None
            if isinstance(raw_retry_errors, (list, tuple, set)):
                try:
                    retry_codes = {int(x) for x in raw_retry_errors}
                except (TypeError, ValueError):
                    retry_codes = None

            should_retry = (
                auto_retry
                and retry_codes is not None
                and int(e.resp.status) in retry_codes
                and not is_last_attempt
            )

            if should_retry:
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

            # Final error handling after retries
            error_result = _handle_final_error(
                e,
                func_name,
                non_critical,
                return_none_on_error,
                response_metadata=response_metadata,
            )
            return error_result

        except Exception as e:
            last_exception = e
            is_last_attempt = attempt == max_retry_attempts

            if auto_retry and not is_last_attempt:
                delay = ERROR_CONFIG["default_backoff_factor"] * (2**attempt)
                logger.warning(
                    "google_api_retrying_generic",
                    function=func_name,
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                time.sleep(delay)
                continue

            error_result = _handle_final_error(
                e,
                func_name,
                non_critical,
                return_none_on_error,
                response_metadata=response_metadata,
            )
            return error_result
    # If we exit the retry loop without returning, use the last captured exception
    if last_exception is None:
        last_exception = Exception("Unknown error after retries")

    error_result = _handle_final_error(
        last_exception,
        func_name,
        non_critical,
        return_none_on_error,
        response_metadata=response_metadata,
    )
    return error_result


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
    service: Resource, requests: List[Tuple], callback_fn: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    Execute multiple API requests in a single batch with enhanced error handling.

    Args:
        service (Resource): The Google service resource.
        requests (list): List of tuples (request_id, api_request).
        callback_fn (callable): Optional callback function for handling responses.

    Returns:
        dict: Dict with results, errors, and summary statistics.

    Example:
        requests = [
            ("user1", service.users().get(userKey="user1@example.com")),
            ("user2", service.users().get(userKey="user2@example.com"))
        ]
        results = execute_batch_request(service, requests)
    """
    results = {}
    errors = {}

    def enhanced_callback(request_id, response, exception):
        if exception:
            error_info = _build_error_info(exception, request_id)
            error_info["timestamp"] = time.time()
            errors[request_id] = error_info
            logger.warning(
                "batch_request_item_failed",
                request_id=request_id,
                error=str(exception),
                status_code=error_info["status_code"],
            )
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

    return {
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


def paginate_all_results(request, resource_key: Optional[str] = None) -> List[dict]:
    """
    Simplified pagination using built-in Google API client features with error handling.

    Args:
        request: The initial API request object.
        resource_key (str): The key in response containing the list (auto-detected if None).

    Returns:
        list: All results from all pages.

    Example:
        request = service.users().list(customer=customer_id)
        all_users = paginate_all_results(request, "users")
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

    return execute_api_call("paginate_all_results", paginate_call)


# Backward compatibility function - simplified version using module-level error handling
def execute_google_api_call(
    service_name: str,
    version: str,
    resource_path: str,
    method: str,
    scopes: Optional[List[str]] = None,
    delegated_user_email: Optional[str] = None,
    single_page: bool = False,
    non_critical: bool = False,
    **kwargs: Any,
) -> Any:
    """
    Simplified version of execute_google_api_call using built-in features and module-level error handling.

    Auto-paginates list operations by default (industry best practice).

    Args:
        service_name (str): The name of the Google service.
        version (str): The version of the Google service.
        resource_path (str): The path to the resource (e.g., "users" or "groups.members").
        method (str): The method to call on the resource.
        scopes (list, optional): The scopes for the Google service.
        delegated_user_email (str, optional): The email address of the user to impersonate.
        single_page (bool, optional): If True, return only one page (override auto-pagination).
        non_critical (bool, optional): Whether to treat errors as non-critical.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        Any: The result of the API call. For list operations, returns all results unless single_page=True.
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
        should_paginate = method == "list" and not single_page

        if should_paginate:
            # Use simplified pagination for list operations
            resource_key = resource_path.split(".")[
                -1
            ]  # e.g., "users" from "users" or "members" from "groups.members"
            return paginate_all_results(request, resource_key)
        else:
            # Simple execution for non-list operations or when single_page=True
            return request.execute()

    # Use module-level error handling
    func_name = f"{service_name}_{version}_{resource_path}_{method}"
    response_metadata = kwargs.pop("response_metadata", False)
    return execute_api_call(
        func_name,
        api_call,
        non_critical=non_critical,
        auto_retry=True,
        return_none_on_error=non_critical,
        response_metadata=response_metadata,
    )


# Backward compatibility - map old decorator name to module-level function
def handle_google_api_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Backward compatibility decorator that points users to the new approach.

    For new code, use module-level functions like get_user(), get_group(), etc.
    or call execute_google_api_call() with non_critical parameter.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Extract function name for logging
        func_name = func.__name__

        # Wrap original function call with module-level error handling
        def api_call():
            return func(*args, **kwargs)

        return execute_api_call(
            func_name,
            api_call,
            non_critical=False,  # Default behavior
            auto_retry=True,
            return_none_on_error=False,
        )

    return wrapper
