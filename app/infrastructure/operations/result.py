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
        cause: BaseException | None -- internal-only diagnostic preserving the original
            exception and its traceback; excluded from repr and equality, and never
            rendered or serialized.
    """

    status: OperationStatus
    message: str | None
    data: T | None = None
    error_code: str | None = None
    retry_after: float | None = None
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
    ) -> OperationResult[T]:
        """Create a SUCCESS OperationResult with optional data.

        Args:
            data: Optional payload to include with the result
            message: Optional success message for logs/operators

        Returns:
            OperationResult with SUCCESS status
        """
        return cls(
            status=OperationStatus.SUCCESS,
            message=message,
            data=data,
        )

    @classmethod
    def error(
        cls,
        status: OperationStatus,
        message: str,
        error_code: str | None = None,
        retry_after: float | None = None,
        data: T | None = None,
    ) -> OperationResult[T]:
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
