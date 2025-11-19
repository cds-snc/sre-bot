"""Operation result dataclass.

Uniform result type returned from operations across the application,
including status, data, and error information.
"""

from typing import Optional, Any
from dataclasses import dataclass

from infrastructure.operations.status import OperationStatus


@dataclass
class OperationResult:
    """Uniform result returned from operations.

    Attributes:
        status: OperationStatus -- high-level outcome
        message: str -- human-friendly message for logs/troubleshooting
        data: Optional[Any] -- optional payload (can be dict, list, or object)
        error_code: Optional[str] -- optional machine error code
        retry_after: Optional[int] -- seconds until retry when rate-limited
    """

    status: OperationStatus
    message: str
    data: Optional[Any] = None
    error_code: Optional[str] = None
    retry_after: Optional[int] = None

    @property
    def is_success(self) -> bool:
        """Helper property to check if operation was successful.

        Returns:
            True if status is SUCCESS, False otherwise
        """
        return self.status == OperationStatus.SUCCESS

    @classmethod
    def success(
        cls, data: Optional[Any] = None, message: str = "ok"
    ) -> "OperationResult":
        """Create a SUCCESS OperationResult with optional data.

        Args:
            data: Optional payload to include with the result
            message: Human-friendly success message

        Returns:
            OperationResult with SUCCESS status
        """
        return cls(status=OperationStatus.SUCCESS, message=message, data=data)

    @classmethod
    def error(
        cls,
        status: OperationStatus,
        message: str,
        error_code: Optional[str] = None,
        retry_after: Optional[int] = None,
        data: Optional[Any] = None,
    ) -> "OperationResult":
        """Create an error OperationResult.

        Args:
            status: OperationStatus indicating error type
            message: Human-friendly error message
            error_code: Optional machine error code
            retry_after: Optional seconds until retry (for rate limiting)
            data: Optional payload to include with the error

        Returns:
            OperationResult with specified error status
        """
        return cls(
            status=status,
            message=message,
            error_code=error_code,
            retry_after=retry_after,
            data=data,
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
