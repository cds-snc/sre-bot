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
from models.integrations import (
    IntegrationResponse,
    build_success_response,
    build_error_response,
)

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


# Helper functions moved to models.integrations for reuse across all integrations


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
) -> IntegrationResponse:
    """Handle the final error after all retries are exhausted. Supports configured non-critical errors which log warnings instead of errors."""
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
            is_non_critical_config = any(
                isinstance(err, str) and (err in error_message) for err in function_errs
            )

    error_code = (
        getattr(error, "response", {}).get("Error", {}).get("Code")
        if hasattr(error, "response")
        else None
    )

    if is_non_critical_config:
        logger.warning(
            "aws_api_non_critical_error",
            function=function_name,
            error=str(error),
            error_code=error_code,
        )
        return build_error_response(error, function_name, "aws")
    else:
        logger.error(
            "aws_api_error_final",
            function=function_name,
            error=str(error),
            error_code=error_code,
        )
        return build_error_response(error, function_name, "aws")


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
    """
    Create a boto3 AWS service client, optionally assuming a role.

    Args:
        service_name (str): The name of the AWS service.
        session_config (dict, optional): Session configuration.
        client_config (dict, optional): Client configuration.
        role_arn (str, optional): The ARN of the IAM role to assume.
        session_name (str): The name for the assumed role session.
    """
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


def _paginate_all_results(
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
    return results


def execute_api_call(
    func_name: str,
    api_call: Callable[[], Any],
    max_retries: Optional[int] = None,
) -> IntegrationResponse:
    """
    Module-level error handling for AWS API calls.

    This provides centralized error handling.

    Args:
        func_name (str): Name of the calling function for logging
        api_call (callable): The API call to execute
        non_critical (bool): Mark this call as non-critical (never raises exceptions)
        auto_retry (bool): Enable automatic retry for retryable errors
        max_retries (int): Override default max retries

    Returns:
        IntegrationResponse: Standardized response model for external API integrations.
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

            return build_success_response(result, func_name, "aws")

        except (BotoCoreError, ClientError) as e:
            last_exception = e

            if _should_retry(e, attempt, max_retry_attempts):
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


def execute_aws_api_call(
    service_name: str,
    method: str,
    keys: Optional[List[str]] = None,
    role_arn: Optional[str] = None,
    session_config: Optional[dict] = None,
    client_config: Optional[dict] = None,
    max_retries: Optional[int] = None,
    force_paginate: bool = False,
    **kwargs,
) -> IntegrationResponse:
    """
    Simplified version of execute_aws_api_call using module-level error handling.

    Auto-paginates list operations by default.

    Args:
        service_name (str): The name of the AWS service.
        method (str): The method to call on the service.
        keys (list, optional): The keys to extract from paginated results.
        role_arn (str, optional): The ARN of the IAM role to assume.
        session_config (dict, optional): Session configuration.
        client_config (dict, optional): Client configuration.
        max_retries (int, optional): Override default max retries.
        force_paginate (bool, optional): If True, force pagination even for single-page results.
        **kwargs: Additional keyword arguments for the API call.

    Returns:
        IntegrationResponse: Standardized response model for external API integrations.
    """

    def api_call():
        client = get_aws_client(service_name, session_config, client_config, role_arn)
        api_method = getattr(client, method)

        # Auto-paginate list operations unless force_paginate is explicitly requested
        should_paginate = (
            force_paginate
            or _can_paginate_method(client, method)
            and not force_paginate
        )

        if should_paginate:
            return _paginate_all_results(client, method, keys, **kwargs)
        else:
            return api_method(**kwargs)

    # Use module-level error handling
    func_name = f"{service_name}_{method}"
    return execute_api_call(
        func_name,
        api_call,
        max_retries=max_retries,
    )
