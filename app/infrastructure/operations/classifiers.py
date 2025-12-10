"""Error classifiers for provider exceptions.

Converts provider-specific exceptions (Google API, AWS SDK, integration layer)
into standardized OperationResult objects. Centralizes error classification
logic to eliminate duplication across providers.

Key Functions:
- classify_http_error(): Google API HTTP errors → OperationResult
- classify_aws_error(): AWS SDK errors → OperationResult
- classify_integration_error(): Provider integration layer errors → OperationResult

Usage:
    from infrastructure.operations.classifiers import (
        classify_http_error,
        classify_aws_error,
        classify_integration_error,
    )

    try:
        result = google_service.members().list(groupKey=group_id).execute()
    except Exception as exc:
        return classify_http_error(exc)
"""

from typing import Optional

from googleapiclient.errors import HttpError
from botocore.exceptions import ClientError

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus


def classify_http_error(exc: Exception) -> OperationResult:
    """Classify Google API HTTP errors into OperationResult.

    Handles googleapiclient.errors.HttpError exceptions by mapping HTTP status
    codes to appropriate OperationStatus values. Extracts retry timing from
    Retry-After headers when available.

    Status Code Mapping:
    - 429: Rate limiting → TRANSIENT_ERROR with retry_after
    - 401: Unauthorized → PERMANENT_ERROR (auth failed)
    - 403: Forbidden → PERMANENT_ERROR (permission denied)
    - 404: Not found → NOT_FOUND
    - 5xx: Server error → TRANSIENT_ERROR
    - Other: Unknown error → PERMANENT_ERROR

    Args:
        exc: Exception raised by Google API client (googleapiclient)

    Returns:
        OperationResult with appropriate status, message, error_code, and
        retry_after (if applicable)

    Example:
        from googleapiclient.errors import HttpError
        from infrastructure.operations.classifiers import classify_http_error

        try:
            result = service.members().list(groupKey="eng@example.com").execute()
        except HttpError as e:
            return classify_http_error(e)
    """
    # Check if this is an HttpError
    if not isinstance(exc, HttpError):
        # Not an HttpError - could be connection error, timeout, etc.
        # Treat as transient (network issues are usually temporary)
        return OperationResult.transient_error(
            f"Connection error: {type(exc).__name__}: {str(exc)}",
            error_code="CONNECTION_ERROR",
        )

    # Extract HTTP status code from response
    status_code: Optional[int] = None
    if hasattr(exc, "resp") and exc.resp:
        status_code = exc.resp.status

    # Handle rate limiting (429 Too Many Requests)
    if status_code == 429:
        retry_after = 60  # Default to 60 seconds

        # Try to extract Retry-After header
        if hasattr(exc, "resp") and hasattr(exc.resp, "get"):
            header_value = exc.resp.get("retry-after")
            if header_value:
                try:
                    retry_after = int(header_value)
                except (ValueError, TypeError):
                    pass  # Use default if header is malformed

        return OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "Google API rate limited",
            error_code="RATE_LIMITED",
            retry_after=retry_after,
        )

    # Handle authentication errors (401 Unauthorized)
    if status_code == 401:
        return OperationResult.permanent_error(
            "Google API authentication failed",
            error_code="UNAUTHORIZED",
        )

    # Handle authorization errors (403 Forbidden)
    if status_code == 403:
        return OperationResult.permanent_error(
            "Google API authorization denied",
            error_code="FORBIDDEN",
        )

    # Handle not found (404)
    if status_code == 404:
        return OperationResult.error(
            OperationStatus.NOT_FOUND,
            "Google resource not found",
            error_code="NOT_FOUND",
        )

    # Handle server errors (5xx)
    if status_code and 500 <= status_code < 600:
        return OperationResult.transient_error(
            f"Google API server error ({status_code})",
            error_code="SERVER_ERROR",
        )

    # Handle other HTTP errors (4xx, other)
    if status_code and 400 <= status_code < 500:
        return OperationResult.permanent_error(
            f"Google API client error ({status_code}): {str(exc)}",
            error_code="HTTP_ERROR",
        )

    # Unknown error - treat as permanent
    return OperationResult.permanent_error(
        f"Google API error: {str(exc)}",
        error_code="UNKNOWN_ERROR",
    )


def classify_aws_error(exc: Exception) -> OperationResult:
    """Classify AWS SDK errors into OperationResult.

    Handles botocore.exceptions.ClientError exceptions by mapping AWS error
    codes to appropriate OperationStatus values. Follows AWS SDK convention
    of treating unknown errors as transient (retry by default).

    Error Code Mapping:
    - ThrottlingException: Rate limiting → TRANSIENT_ERROR with retry_after
    - AccessDeniedException: Permission denied → PERMANENT_ERROR
    - ResourceNotFoundException: Not found → NOT_FOUND
    - ValidationException: Bad input → PERMANENT_ERROR
    - Other: Unknown error → TRANSIENT_ERROR (AWS convention)

    Args:
        exc: Exception raised by AWS SDK (boto3/botocore)

    Returns:
        OperationResult with appropriate status, message, error_code, and
        retry_after (if applicable)

    Example:
        from botocore.exceptions import ClientError
        from infrastructure.operations.classifiers import classify_aws_error

        try:
            response = client.list_group_memberships(
                IdentityStoreId=store_id,
                GroupId=group_id
            )
        except ClientError as e:
            return classify_aws_error(e)
    """
    # Check if this is a ClientError
    if not isinstance(exc, ClientError):
        # Could be BotoCoreError (connection), timeout, etc.
        # Treat as transient (network issues are usually temporary)
        return OperationResult.transient_error(
            f"AWS connection error: {type(exc).__name__}: {str(exc)}",
            error_code="CONNECTION_ERROR",
        )

    # Extract error code from response
    error_code = "Unknown"
    if hasattr(exc, "response") and exc.response:
        error_info = exc.response.get("Error", {})
        error_code = error_info.get("Code", "Unknown")

    # Handle rate limiting (ThrottlingException)
    if error_code == "ThrottlingException":
        return OperationResult.error(
            OperationStatus.TRANSIENT_ERROR,
            "AWS API throttled",
            error_code="RATE_LIMITED",
            retry_after=60,  # AWS recommends 60s default
        )

    # Handle permission denied (AccessDeniedException)
    if error_code == "AccessDeniedException":
        return OperationResult.permanent_error(
            "AWS API access denied",
            error_code="FORBIDDEN",
        )

    # Handle resource not found (ResourceNotFoundException)
    if error_code == "ResourceNotFoundException":
        return OperationResult.error(
            OperationStatus.NOT_FOUND,
            "AWS resource not found",
            error_code="NOT_FOUND",
        )

    # Handle validation errors (bad input)
    if error_code in (
        "ValidationException",
        "InvalidParameterException",
        "BadRequestException",
    ):
        return OperationResult.permanent_error(
            f"AWS validation error: {error_code}",
            error_code="INVALID_REQUEST",
        )

    # AWS SDK convention: Unknown errors are transient (retry by default)
    # This is because AWS services are highly reliable and most failures
    # are temporary (timeouts, service degradation, etc.)
    return OperationResult.transient_error(
        f"AWS client error: {error_code}",
        error_code="AWS_CLIENT_ERROR",
    )


def classify_integration_error(exc: Exception) -> OperationResult:
    """Classify provider integration layer errors into OperationResult.

    Handles IntegrationError exceptions raised by provider adapters when their
    underlying integration (Google, AWS, etc.) reports an error. Extracts context
    from the IntegrationError.response attribute (which is itself an OperationResult)
    to provide more specific classification.

    This function bridges the gap between integration layer errors (OperationResult
    objects) and provider-level error handling.

    Args:
        exc: IntegrationError or other exception from provider integration

    Returns:
        OperationResult with appropriate status, message, error_code, and
        retry_after (if applicable)

    Example:
        from modules.groups.domain.errors import IntegrationError
        from infrastructure.operations.classifiers import classify_integration_error

        try:
            resp = google_directory.insert_member(group_key, email)
            if not resp.is_success:
                raise IntegrationError("google insert_member failed", response=resp)
        except IntegrationError as e:
            return classify_integration_error(e)
    """
    # Check if this is an IntegrationError (avoid circular import by using duck typing)
    if not (hasattr(exc, "response") and hasattr(exc, "args")):
        # Not an IntegrationError - could be another exception
        # Treat as transient (network issues are usually temporary)
        return OperationResult.transient_error(
            f"Integration error: {type(exc).__name__}: {str(exc)}",
            error_code="INTEGRATION_ERROR",
        )

    # Extract the response attribute (which is an OperationResult)
    response = getattr(exc, "response", None)

    # If response is an OperationResult, return it directly
    # (it already has proper classification)
    if isinstance(response, OperationResult):
        return response

    # If response is not an OperationResult but some other API response object,
    # treat as integration error with message from IntegrationError
    message = str(exc) if exc.args else "Integration error"
    return OperationResult.permanent_error(
        f"Integration failed: {message}",
        error_code="INTEGRATION_ERROR",
    )
