"""
AWS Service Next Module

This module provides centralized error handling, retry logic, standardized responses, and simplified pagination for AWS API calls, inspired by the Google Service Next module.

Features:
- Centralized error handling and retry logic
- Standardized response format for consistent debugging
- Simplified pagination for list operations

Note:
Unlike Google APIs, AWS/boto3 does NOT support generic batch API calls for unrelated operations. Each API call is a separate HTTP request. Some AWS services (like DynamoDB, SQS, S3) provide service-specific batch operations, but there is no universal batch API for arbitrary calls (e.g., Identity Store, SSO Admin, etc.).

Usage:
    # Simple usage (auto-paginates list operations by default)
    instances = execute_aws_api_call(
        service_name="ec2",
        method="describe_instances",
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}],
    )

    # Single page only (override auto-pagination)
    single_page = execute_aws_api_call(
        service_name="ec2",
        method="describe_instances",
        single_page=True,
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}],
    )

    # With standardized response format for better debugging
    response = execute_aws_api_call(
        service_name="ec2",
        method="describe_instances",
        response_metadata=True,
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}],
    )
    # response = {"success": True, "data": {...}, "error": None, "function_name": "ec2_describe_instances"}
"""

import time
from typing import Any, List, Optional, Callable, cast

import boto3  # type: ignore
from botocore.client import BaseClient  # type: ignore
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
from core.config import settings
from core.logging import get_module_logger

logger = get_module_logger()

AWS_REGION = settings.aws.AWS_REGION
THROTTLING_ERRS = settings.aws.THROTTLING_ERRS
RESOURCE_NOT_FOUND_ERRS = settings.aws.RESOURCE_NOT_FOUND_ERRS

ERROR_CONFIG = {
    "non_critical_errors": {
        "get_user": ["not found", "timed out"],
        "describe_user": ["not found", "user not found"],
        "get_group": ["not found", "group not found"],
        "describe_group": ["not found", "group not found"],
        "get_role": ["not found", "role not found"],
        "describe_role": ["not found", "role not found"],
    },
    "retry_errors": [
        "Throttling",
        "RequestLimitExceeded",
        "ProvisionedThroughputExceededException",
    ],
    "rate_limit_delay": 5,
    "default_max_retries": 3,
    "default_backoff_factor": 1.0,
}


class AWSAPIError(Exception):
    """Custom exception for AWS API errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        function_name: Optional[str] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.function_name = function_name
        super().__init__(message)


def _build_error_info(error: Exception, function_name: str) -> dict:
    error_code = (
        getattr(error, "response", {}).get("Error", {}).get("Code")
        if hasattr(error, "response")
        else None
    )
    return {
        "message": str(error),
        "error_code": error_code,
        "function_name": function_name,
    }


def _build_response(
    success: bool, data: Any, error_info: Optional[dict], function_name: str
) -> dict:
    return {
        "success": success,
        "data": data,
        "error": error_info,
        "function_name": function_name,
    }


def _should_retry(error: Exception, attempt: int, max_attempts: int) -> bool:
    error_code = (
        getattr(error, "response", {}).get("Error", {}).get("Code")
        if hasattr(error, "response")
        else None
    )
    retry_errors = ERROR_CONFIG.get("retry_errors", [])
    if not isinstance(retry_errors, (list, set, tuple)):
        retry_errors = []
    return error_code in retry_errors and attempt < max_attempts


def _calculate_retry_delay(attempt: int) -> float:
    backoff_obj = ERROR_CONFIG.get("default_backoff_factor", 0.5)
    try:
        # Cast to Any so type checkers accept passing it to float()
        backoff = float(cast(Any, backoff_obj))
    except (TypeError, ValueError):
        backoff = 0.5  # fallback to default
    return backoff * (2**attempt)


def _handle_final_error(
    error: Exception,
    function_name: str,
    non_critical: bool = False,
    return_none_on_error: bool = False,
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

    error_code = (
        getattr(error, "response", {}).get("Error", {}).get("Code")
        if hasattr(error, "response")
        else None
    )

    if is_non_critical:
        logger.warning(
            "aws_api_non_critical_error",
            function=function_name,
            error=str(error),
            error_code=error_code,
        )
        if response_metadata:
            return _build_response(
                False, None, _build_error_info(error, function_name), function_name
            )
        return None
    else:
        logger.error(
            "aws_api_error_final",
            function=function_name,
            error=str(error),
            error_code=error_code,
        )
        if return_none_on_error:
            if response_metadata:
                return _build_response(
                    False, None, _build_error_info(error, function_name), function_name
                )
            return None
        # For job safety, never raise exceptions by default
        if response_metadata:
            return _build_response(
                False, None, _build_error_info(error, function_name), function_name
            )
        return None


def _can_paginate_method(client: BaseClient, method: str) -> bool:
    """
    Determine if an AWS API method can be paginated using the client's can_paginate method.

    Args:
        client (BaseClient): The AWS service client
        method (str): The AWS API method name

    Returns:
        bool: True if the method can be paginated
    """
    try:
        return client.can_paginate(method)
    except (AttributeError, TypeError, ValueError):
        # Fallback to False if method doesn't exist or can't be checked
        return False


def get_aws_client(
    service_name: str,
    session_config: Optional[dict] = None,
    client_config: Optional[dict] = None,
    role_arn: Optional[str] = None,
    session_name: str = "DefaultSession",
) -> BaseClient:
    session_config = session_config or {"region_name": AWS_REGION}
    client_config = client_config or {"region_name": AWS_REGION}
    if role_arn:
        sts_client = boto3.client("sts")
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn, RoleSessionName=session_name
        )
        credentials = assumed_role["Credentials"]
        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
            **session_config,
        )
    else:
        session = boto3.Session(**session_config)
    return session.client(service_name, **client_config)


def paginate_all_results(
    client: BaseClient, method: str, keys: Optional[List[str]] = None, **kwargs
) -> List[dict]:
    paginator = client.get_paginator(method)
    results = []
    for page in paginator.paginate(**kwargs):
        if keys is None:
            for key, value in page.items():
                if key != "ResponseMetadata":
                    if isinstance(value, list):
                        results.extend(value)
                    else:
                        results.append(value)
        else:
            for key in keys:
                if key in page:
                    results.extend(page[key])
    logger.info("pagination_completed", total_results=len(results))
    return results


def execute_api_call(
    func_name: str,
    api_call: Callable[[], Any],
    non_critical: bool = False,
    return_none_on_error: bool = False,
    auto_retry: bool = True,
    max_retries: Optional[int] = None,
    response_metadata: bool = False,
) -> Any:
    """
    Module-level error handling for AWS API calls.

    This provides centralized error handling similar to Google's execute_api_call.

    Args:
        func_name (str): Name of the calling function for logging
        api_call (callable): The API call to execute
        non_critical (bool): Mark this call as non-critical (never raises exceptions)
        return_none_on_error (bool): Return None instead of raising on errors
        auto_retry (bool): Enable automatic retry for retryable errors
        max_retries (int): Override default max retries
        response_metadata (bool): Return standardized response dict

    Returns:
        Any: The result of the API call or standardized response dict
    """
    default_retries = ERROR_CONFIG.get("default_max_retries", 3)
    max_retry_attempts = (
        max_retries if max_retries is not None else cast(int, default_retries)
    )
    last_exception: Optional[Exception] = None

    for attempt in range(max_retry_attempts + 1):
        try:
            logger.debug(
                "aws_api_call_start",
                function=func_name,
                attempt=attempt + 1,
                max_attempts=max_retry_attempts + 1,
            )

            result = api_call()

            if attempt > 0:
                logger.info(
                    "aws_api_retry_success",
                    function=func_name,
                    attempt=attempt + 1,
                )

            if response_metadata:
                return _build_response(True, result, None, func_name)
            return result

        except (BotoCoreError, ClientError) as e:
            last_exception = e

            if auto_retry and _should_retry(e, attempt, max_retry_attempts):
                delay = _calculate_retry_delay(attempt)
                logger.warning(
                    "aws_api_retrying",
                    function=func_name,
                    attempt=attempt + 1,
                    error=str(e),
                    delay=delay,
                )
                time.sleep(delay)
                continue

            return _handle_final_error(
                e,
                func_name,
                non_critical,
                return_none_on_error,
                response_metadata=response_metadata,
            )

        except Exception as e:  # pylint: disable=broad-except
            last_exception = e

            return _handle_final_error(
                e,
                func_name,
                non_critical,
                return_none_on_error,
                response_metadata=response_metadata,
            )

    # If we exit the retry loop without returning, use the last captured exception
    if last_exception is None:
        last_exception = Exception("Unknown error after retries")

    return _handle_final_error(
        last_exception,
        func_name,
        non_critical,
        return_none_on_error,
        response_metadata=response_metadata,
    )


def execute_aws_api_call(
    service_name: str,
    method: str,
    keys: Optional[List[str]] = None,
    role_arn: Optional[str] = None,
    session_config: Optional[dict] = None,
    client_config: Optional[dict] = None,
    max_retries: Optional[int] = None,
    non_critical: bool = False,
    return_none_on_error: bool = False,
    response_metadata: bool = False,
    single_page: bool = False,
    **kwargs,
) -> Any:
    """
    Simplified version of execute_aws_api_call using module-level error handling.

    Auto-paginates list operations by default (industry best practice).

    Args:
        service_name (str): The name of the AWS service.
        method (str): The method to call on the service.
        keys (list, optional): The keys to extract from paginated results.
        role_arn (str, optional): The ARN of the IAM role to assume.
        session_config (dict, optional): Session configuration.
        client_config (dict, optional): Client configuration.
        max_retries (int, optional): Override default max retries.
        non_critical (bool): Mark this call as non-critical (never raises exceptions).
        return_none_on_error (bool): Return None instead of raising on errors.
        response_metadata (bool): Return standardized response dict.
        single_page (bool, optional): If True, return only one page (override auto-pagination).
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        Any: The result of the API call or standardized response dict.
    """

    def api_call():
        client = get_aws_client(service_name, session_config, client_config, role_arn)
        api_method = getattr(client, method)

        # Auto-paginate list operations unless single_page is explicitly requested
        should_paginate = _can_paginate_method(client, method) and not single_page

        if should_paginate:
            return paginate_all_results(client, method, keys, **kwargs)
        else:
            return api_method(**kwargs)

    # Use module-level error handling
    func_name = f"{service_name}_{method}"
    return execute_api_call(
        func_name,
        api_call,
        non_critical=non_critical,
        return_none_on_error=return_none_on_error,
        auto_retry=True,
        max_retries=max_retries,
        response_metadata=response_metadata,
    )
