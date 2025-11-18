from typing import Any, Optional

from pydantic import BaseModel


class IntegrationResponse(BaseModel):
    """
    Standardized response model for external API integrations.

    This docstring describes the purpose and fields of the IntegrationResponse model used
    to convey the outcome of an integration call in a consistent format.

    Attributes:
        success (bool): True if the integration call succeeded, False otherwise.
        data (Optional[Any]): The payload returned by the integration on success. The exact
            structure depends on the integration and may be None when there is no data.
        error (Optional[dict]): Error information provided when success is False. Typically
            includes keys such as 'code', 'message', and any integration-specific details.
        function_name (str): The identifier or human-readable name of the integration
            that produced this response (e.g., "stripe", "github", "internal_service").
        integration_name (str): The name of the integration (e.g., "aws", "google", "stripe").
    """

    success: bool
    function_name: str
    integration_name: str
    data: Optional[Any]
    error: Optional[dict]
    model_config = {"extra": "ignore"}


def build_error_info(error: Exception, function_name: str) -> dict:
    """
    Build standardized error information dictionary from an exception.

    Args:
        error (Exception): The exception that occurred
        function_name (str): Name of the function where the error occurred

    Returns:
        dict: Standardized error information with message, error_code, and function_name
    """
    error_code = None

    # Extract error code for AWS/boto3 errors
    if hasattr(error, "response"):
        error_code = getattr(error, "response", {}).get("Error", {}).get("Code")

    # Extract error code for Google API errors
    elif hasattr(error, "resp") and hasattr(error.resp, "status"):
        error_code = str(error.resp.status)

    # Extract error code for HTTP errors
    elif hasattr(error, "status_code"):
        error_code = str(error.status_code)

    return {
        "message": str(error),
        "error_code": error_code,
        "function_name": function_name,
    }


def build_integration_response(
    success: bool,
    data: Any,
    error_info: Optional[dict],
    function_name: str,
    integration_name: str,
) -> IntegrationResponse:
    """
    Build a standardized integration response.

    Args:
        success (bool): Whether the operation succeeded
        data (Any): The response data (None for errors)
        error_info (Optional[dict]): Error information if success is False
        function_name (str): Name of the function that was called
        integration_name (str): Name of the integration (aws, google, etc.)

    Returns:
        IntegrationResponse: Standardized response object
    """
    return IntegrationResponse(
        success=success,
        data=data,
        error=error_info,
        function_name=function_name,
        integration_name=integration_name,
    )


def build_success_response(
    data: Any, function_name: str, integration_name: str
) -> IntegrationResponse:
    """
    Build a successful integration response.

    Args:
        data (Any): The response data
        function_name (str): Name of the function that was called
        integration_name (str): Name of the integration

    Returns:
        IntegrationResponse: Standardized success response
    """
    return build_integration_response(
        success=True,
        data=data,
        error_info=None,
        function_name=function_name,
        integration_name=integration_name,
    )


def build_error_response(
    error: Exception, function_name: str, integration_name: str
) -> IntegrationResponse:
    """
    Build an error integration response from an exception.

    Args:
        error (Exception): The exception that occurred
        function_name (str): Name of the function where the error occurred
        integration_name (str): Name of the integration

    Returns:
        IntegrationResponse: Standardized error response
    """
    error_info = build_error_info(error, function_name)
    return build_integration_response(
        success=False,
        data=None,
        error_info=error_info,
        function_name=function_name,
        integration_name=integration_name,
    )
