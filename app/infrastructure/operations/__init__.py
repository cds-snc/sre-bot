"""Operation result types and status enums.

This module contains standardized result types for operations across
the application: the status enum and the result dataclass.
"""

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

__all__ = [
    "OperationResult",
    "OperationStatus",
]
