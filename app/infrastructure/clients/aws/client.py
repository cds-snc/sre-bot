"""Base AWS client utilities for infrastructure clients.

Provides `get_boto3_client` and `execute_aws_api_call` with the
OperationResult pattern. This module intentionally avoids reading
settings at import time and accepts configuration via parameters.
"""

import time
from typing import Any, Callable, Dict, List, Optional

import boto3  # type: ignore
from botocore.client import BaseClient  # type: ignore
from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
import structlog

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

logger = structlog.get_logger()


def get_boto3_client(
    service_name: str,
    session_config: Optional[Dict[str, Any]] = None,
    client_config: Optional[Dict[str, Any]] = None,
    role_arn: Optional[str] = None,
    session_name: str = "InfraClientSession",
) -> BaseClient:
    """Create a boto3 client for the given service.

    Args:
        service_name: AWS service name (e.g., 'dynamodb')
        session_config: Optional boto3 session kwargs (e.g., region_name)
        client_config: Optional client kwargs (e.g., endpoint_url)
        role_arn: Optional role to assume for cross-account access
        session_name: Name for assumed role session

    Returns:
        botocore client instance
    """
    session_config = session_config or {}
    client_config = client_config or {}

    if role_arn:
        sts = boto3.client("sts")
        assumed = sts.assume_role(RoleArn=role_arn, RoleSessionName=session_name)
        creds = assumed["Credentials"]
        session = boto3.Session(
            aws_access_key_id=creds["AccessKeyId"],
            aws_secret_access_key=creds["SecretAccessKey"],
            aws_session_token=creds["SessionToken"],
            **session_config,
        )
    else:
        session = boto3.Session(**session_config)

    return session.client(service_name, **client_config)


def _calculate_retry_delay(attempt: int, backoff_factor: float = 0.5) -> float:
    return backoff_factor * (2**attempt)


def _call_api_once(
    service_name: str,
    method: str,
    keys: Optional[List[str]],
    role_arn: Optional[str],
    session_config: Optional[Dict[str, Any]],
    client_config: Optional[Dict[str, Any]],
    force_paginate: bool,
    kwargs: Dict[str, Any],
) -> Any:
    client = get_boto3_client(
        service_name,
        session_config=session_config,
        client_config=client_config,
        role_arn=role_arn,
    )
    api_method = getattr(client, method)

    if force_paginate and hasattr(client, "get_paginator"):
        paginator = client.get_paginator(method)
        results: List[Any] = []
        for page in paginator.paginate(**kwargs):
            if keys:
                for k in keys:
                    if k in page and isinstance(page[k], list):
                        results.extend(page[k])
            else:
                for k, v in page.items():
                    if k == "ResponseMetadata":
                        continue
                    if isinstance(v, list):
                        results.extend(v)
                    else:
                        results.append(v)
        return results

    return api_method(**kwargs)


def _map_client_error(
    e: ClientError,
    service_name: str,
    method: str,
    treat_conflict_as_success: bool,
    conflict_callback: Optional[Callable[[Exception], None]],
) -> OperationResult:
    error_code = e.response.get("Error", {}).get("Code")
    error_message = e.response.get("Error", {}).get("Message", str(e))

    if error_code in (
        "ResourceAlreadyExistsException",
        "EntityAlreadyExists",
        "ConflictException",
    ):
        logger.info(
            "aws_api_conflict",
            service=service_name,
            method=method,
            code=error_code,
            message=error_message,
        )
        if conflict_callback:
            try:
                conflict_callback(e)
            except Exception:
                logger.exception("conflict_callback_failed", error=str(e))

        if treat_conflict_as_success:
            return OperationResult.success(data=None, message=error_message)

        return OperationResult.permanent_error(
            message=error_message, error_code=error_code
        )

    if error_code in ("ThrottlingException", "RequestLimitExceeded"):
        retry_after = None
        try:
            retry_after = int(e.response.get("RetryAfter", 0))
        except Exception:
            retry_after = None
        return OperationResult.transient_error(
            message=error_message, error_code=error_code, retry_after=retry_after
        )

    if error_code in ("AccessDeniedException", "UnauthorizedOperation"):
        return OperationResult.error(
            OperationStatus.UNAUTHORIZED, message=error_message
        )

    return OperationResult.permanent_error(message=error_message, error_code=error_code)


def execute_aws_api_call(
    service_name: str,
    method: str,
    keys: Optional[List[str]] = None,
    role_arn: Optional[str] = None,
    session_config: Optional[Dict[str, Any]] = None,
    client_config: Optional[Dict[str, Any]] = None,
    max_retries: int = 3,
    force_paginate: bool = False,
    backoff_factor: float = 0.5,
    treat_conflict_as_success: bool = False,
    conflict_callback: Optional[Callable[[Exception], None]] = None,
    **kwargs,
) -> OperationResult:
    """Execute an AWS API call with retries and standardized results.

    Args mirror `boto3` call parameters; the function returns an
    `OperationResult` object for consistent downstream handling.
    """

    last_exc: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            result = _call_api_once(
                service_name,
                method,
                keys,
                role_arn,
                session_config,
                client_config,
                force_paginate,
                kwargs,
            )
            return OperationResult.success(
                data=result, message=f"{service_name}.{method} succeeded"
            )

        except ClientError as e:
            last_exc = e
            mapped = _map_client_error(
                e, service_name, method, treat_conflict_as_success, conflict_callback
            )

            # If conflict was treated as success, return success result immediately
            if mapped.is_success:
                return mapped

            # Retry on transient errors if attempts remain
            if (
                mapped.status == OperationStatus.TRANSIENT_ERROR
                and attempt < max_retries
            ):
                delay = _calculate_retry_delay(attempt, backoff_factor)
                logger.warning(
                    "aws_api_retry",
                    service=service_name,
                    method=method,
                    attempt=attempt + 1,
                    error=str(e),
                    delay=delay,
                )
                time.sleep(delay)
                continue

            logger.error(
                "aws_api_error_final", service=service_name, method=method, error=str(e)
            )
            return mapped

        except (BotoCoreError, Exception) as e:  # pylint: disable=broad-except
            last_exc = e
            logger.error(
                "aws_api_unexpected_error",
                service=service_name,
                method=method,
                error=str(e),
            )
            return OperationResult.permanent_error(message=str(e))

    return OperationResult.permanent_error(
        message=str(last_exc) if last_exc else "unknown_error"
    )
