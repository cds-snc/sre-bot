"""Operation result types and status enums.

This module contains standardized result types for operations across
the application, including status enums, result dataclasses, and error
classifiers for provider exceptions.
"""

from infrastructure.operations.classifiers import (
    classify_aws_error,
    classify_http_error,
    classify_integration_error,
)
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

__all__ = [
    "OperationResult",
    "OperationStatus",
    "classify_http_error",
    "classify_aws_error",
    "classify_integration_error",
]
