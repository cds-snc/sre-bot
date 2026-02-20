"""Operation result dataclass.

Uniform result type returned from operations across the application,
including status, data, and error information.

Implements Railway-Oriented Programming pattern for type-safe error handling.
See: docs/decisions/tier-1-foundation/ADR-001-operation-result-pattern.md
"""

from typing import Optional, Any, Callable, TypeVar
from dataclasses import dataclass

from infrastructure.operations.status import OperationStatus

# Type variables for generic helper methods
T = TypeVar("T")
U = TypeVar("U")


@dataclass
class OperationResult:
    """Uniform result returned from operations.

    Implements Railway-Oriented Programming pattern for functional error handling.
    Provides type-safe composition via map() and bind() methods.

    Attributes:
        status: OperationStatus -- high-level outcome
        message: str -- human-friendly message for logs/troubleshooting
        data: Optional[Any] -- optional payload (can be dict, list, or object)
        error_code: Optional[str] -- optional machine error code
        retry_after: Optional[int] -- seconds until retry when rate-limited
        provider: Optional[str] -- provider name for observability (e.g., 'google', 'aws')
        operation: Optional[str] -- operation name for observability (e.g., 'list_members')
    """

    status: OperationStatus
    message: str
    data: Optional[Any] = None
    error_code: Optional[str] = None
    retry_after: Optional[int] = None
    provider: Optional[str] = None
    operation: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """Helper property to check if operation was successful.

        Returns:
            True if status is SUCCESS, False otherwise
        """
        return self.status == OperationStatus.SUCCESS

    @classmethod
    def success(
        cls,
        data: Optional[Any] = None,
        message: str = "ok",
        provider: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> "OperationResult":
        """Create a SUCCESS OperationResult with optional data.

        Args:
            data: Optional payload to include with the result
            message: Human-friendly success message
            provider: Optional provider name for observability
            operation: Optional operation name for observability

        Returns:
            OperationResult with SUCCESS status
        """
        return cls(
            status=OperationStatus.SUCCESS,
            message=message,
            data=data,
            provider=provider,
            operation=operation,
        )

    @classmethod
    def error(
        cls,
        status: OperationStatus,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
        data: Optional[Any] = None,
        provider: Optional[str] = None,
        operation: Optional[str] = None,
    ) -> "OperationResult":
        """Create an error OperationResult.

        Args:
            status: OperationStatus indicating error type
            message: Human-friendly error message
            error_code: Optional machine error code
            retry_after: Optional seconds until retry (for rate limiting)
            data: Optional payload to include with the error
            provider: Optional provider name for observability
            operation: Optional operation name for observability

        Returns:
            OperationResult with specified error status
        """
        return cls(
            status=status,
            message=message,
            error_code=error_code,
            retry_after=retry_after,
            data=data,
            provider=provider,
            operation=operation,
        )

    @classmethod
    def transient_error(
        cls,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
    ) -> "OperationResult":
        """Create a transient (retryable) error result.

        Use for errors that may succeed on retry, such as:
        - Network timeouts
        - Rate limiting
        - Temporary service unavailability

        Args:
            message: Human-friendly error message
            error_code: Optional machine error code
            retry_after: Optional seconds until retry

        Returns:
            OperationResult with TRANSIENT_ERROR status
        """
        return cls.error(
            OperationStatus.TRANSIENT_ERROR, message, error_code, retry_after
        )

    @classmethod
    def permanent_error(
        cls, message: str, error_code: Optional[str] = None
    ) -> "OperationResult":
        """Create a permanent (non-retryable) error result.

        Use for errors that will not succeed on retry, such as:
        - Validation errors
        - Authentication/authorization failures
        - Resource not found
        - Invalid input

        Args:
            message: Human-friendly error message
            error_code: Optional machine error code

        Returns:
            OperationResult with PERMANENT_ERROR status
        """
        return cls.error(OperationStatus.PERMANENT_ERROR, message, error_code)

    def map(self, fn: Callable[[Any], Any]) -> "OperationResult":
        """Apply a function to the success value (Railway-Oriented Programming).

        If the result is successful, applies the function to data and returns
        a new OperationResult with the transformed data. If the result is an
        error, returns self unchanged.

        Args:
            fn: Function to apply to the success value

        Returns:
            New OperationResult with transformed data, or self if error

        Example:
            result = OperationResult.success(data=5)
            doubled = result.map(lambda x: x * 2)  # Success with data=10

            error = OperationResult.permanent_error("failed")
            still_error = error.map(lambda x: x * 2)  # Still an error
        """
        if self.is_success:
            return OperationResult.success(
                data=fn(self.data),
                message=self.message,
                provider=self.provider,
                operation=self.operation,
            )
        return self

    def bind(self, fn: Callable[[Any], "OperationResult"]) -> "OperationResult":
        """Chain operations that return OperationResult (Railway-Oriented Programming).

        If the result is successful, applies the function to data and returns
        the resulting OperationResult. If the result is an error, returns self
        unchanged. This enables chaining multiple operations that may fail.

        Args:
            fn: Function that takes the success value and returns OperationResult

        Returns:
            OperationResult from fn, or self if error

        Example:
            def validate_user(user_id: int) -> OperationResult:
                if user_id > 0:
                    return OperationResult.success(data=user_id)
                return OperationResult.permanent_error("Invalid ID")

            def fetch_user(user_id: int) -> OperationResult:
                # ... fetch from database
                return OperationResult.success(data={"id": user_id, "name": "Alice"})

            result = (
                OperationResult.success(data=123)
                .bind(validate_user)
                .bind(fetch_user)
            )
        """
        if self.is_success:
            return fn(self.data)
        return self

    def unwrap_or(self, default: Any) -> Any:
        """Get the success value or return a default.

        Args:
            default: Value to return if this is an error

        Returns:
            The data if successful, otherwise the default value

        Example:
            result = OperationResult.success(data=42)
            value = result.unwrap_or(0)  # Returns 42

            error = OperationResult.permanent_error("failed")
            value = error.unwrap_or(0)  # Returns 0
        """
        return self.data if self.is_success else default

    def unwrap(self) -> Any:
        """Get the success value or raise an exception.

        Returns:
            The data if successful

        Raises:
            ValueError: If the result is an error

        Example:
            result = OperationResult.success(data=42)
            value = result.unwrap()  # Returns 42

            error = OperationResult.permanent_error("failed")
            value = error.unwrap()  # Raises ValueError
        """
        if not self.is_success:
            raise ValueError(
                f"Called unwrap() on error result: {self.message} "
                f"(code: {self.error_code}, status: {self.status.value})"
            )
        return self.data
