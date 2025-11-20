"""Operation result types and status enums.

This module contains standardized result types for operations across
the application, including status enums and result dataclasses.
"""

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

__all__ = [
    "OperationResult",
    "OperationStatus",
]
