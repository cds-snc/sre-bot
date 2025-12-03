"""Operation status enumeration.

Status codes for operation results, used to classify outcomes of operations
across the application for appropriate error handling and retries.
"""

from enum import Enum


class OperationStatus(Enum):
    """Status codes for operation results.

    Attributes:
        SUCCESS: Operation completed successfully
        TRANSIENT_ERROR: Retryable error (network, timeout, rate limit)
        PERMANENT_ERROR: Non-retryable error (validation, auth, not found)
        UNAUTHORIZED: Authentication or authorization failure
        NOT_FOUND: Resource not found
    """

    SUCCESS = "success"
    TRANSIENT_ERROR = "transient_error"
    PERMANENT_ERROR = "permanent_error"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
