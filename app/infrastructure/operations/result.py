"""Operation result dataclass.

Uniform, immutable result envelope returned at integration and service
boundaries, carrying status, data and error information. Consumers branch with
``match result.status:`` and ``typing.assert_never`` on the fall-through.

See: decisions/operation-result.md
"""

from dataclasses import dataclass, field

from infrastructure.operations.status import OperationStatus


@dataclass(frozen=True)
class OperationResult[T]:
    """Uniform result returned from operations.

    Attributes:
        status: OperationStatus -- high-level outcome
        message: str | None -- message for logs/operators; optional on SUCCESS
        data: T | None -- optional payload for successful results
        error_code: str | None -- optional machine error code
        retry_after: float | None -- seconds until retry, only when upstream gave a hint
        provider: str | None -- provider name for observability (e.g., 'google', 'aws').
            Kept for observability; scheduled for removal in TASK-105.1, which is not part
            of the decisions/operation-result.md canonical shape.
        operation: str | None -- operation name for observability (e.g., 'list_members').
            Kept for observability; scheduled for removal in TASK-105.1, which is not part
            of the decisions/operation-result.md canonical shape.
        cause: BaseException | None -- internal-only diagnostic preserving the original
            exception and its traceback; excluded from repr and equality, and never
            rendered or serialized.
    """

    status: OperationStatus
    message: str | None
    data: T | None = None
    error_code: str | None = None
    retry_after: float | None = None
    provider: str | None = None
    operation: str | None = None
    cause: BaseException | None = field(default=None, repr=False, compare=False)

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
        data: T | None = None,
        message: str | None = None,
        provider: str | None = None,
        operation: str | None = None,
    ) -> OperationResult[T]:
        """Create a SUCCESS OperationResult with optional data.

        Args:
            data: Optional payload to include with the result
            message: Optional success message for logs/operators
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
        error_code: str | None = None,
        retry_after: float | None = None,
        data: T | None = None,
        provider: str | None = None,
        operation: str | None = None,
    ) -> OperationResult[T]:
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
        error_code: str | None = None,
        retry_after: float | None = None,
    ) -> OperationResult[T]:
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
        return cls.error(OperationStatus.TRANSIENT_ERROR, message, error_code, retry_after)

    @classmethod
    def permanent_error(cls, message: str, error_code: str | None = None) -> OperationResult[T]:
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
