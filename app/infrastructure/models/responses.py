"""Standard API response wrappers for consistent response formatting.

This module provides generic response wrapper classes used across the application
to ensure consistent response structures across all API endpoints.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Generic API response wrapper.

    Used for successful responses that may contain arbitrary data.

    Attributes:
        success: Whether the operation succeeded
        data: Response payload (type variable, can be any type)
        message: Optional human-readable message
        error_code: Optional machine-readable error code

    Example:
        >>> response = APIResponse(
        ...     success=True,
        ...     data={"user_id": "123", "name": "John"},
        ...     message="User created successfully"
        ... )
        >>> response.model_dump_json()
        '{"success":true,"data":{"user_id":"123","name":"John"},...'
    """

    success: bool = Field(..., description="Whether the operation succeeded")
    data: T | None = Field(default=None, description="Response payload (type variable)")
    message: str | None = Field(
        default=None, description="Optional human-readable message"
    )
    error_code: str | None = Field(
        default=None, description="Optional machine-readable error code"
    )


class ErrorResponse(BaseModel):
    """Standard error response wrapper.

    Used for error responses with consistent error information.

    Attributes:
        success: Always False for error responses
        error: Human-readable error message
        error_code: Machine-readable error code for error handling
        details: Optional additional error details (e.g., validation errors)

    Example:
        >>> error = ErrorResponse(
        ...     error="Validation failed",
        ...     error_code="VALIDATION_ERROR",
        ...     details={"email": "Invalid email format"}
        ... )
        >>> error.model_dump_json()
        '{"success":false,"error":"Validation failed",...'
    """

    success: bool = Field(default=False, description="Always False for error responses")
    error: str = Field(..., description="Human-readable error message")
    error_code: str = Field(..., description="Machine-readable error code")
    details: dict[str, Any] | None = Field(
        default=None, description="Optional additional error details"
    )
