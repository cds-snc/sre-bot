"""Operation result types and status enums.

This module contains standardized result types for operations across
the application: the status enum, the result dataclass and the error-code
registry.
"""

from infrastructure.operations.codes import ErrorCode
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

__all__ = [
    "ErrorCode",
    "OperationResult",
    "OperationStatus",
]
