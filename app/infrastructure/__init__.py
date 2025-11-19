"""Infrastructure layer for shared, reusable components.

This layer contains cross-cutting concerns and infrastructure patterns
extracted from modules for app-wide use:

- resilience/: Circuit breaker and resilience patterns
- operations/: Operation result types and status enums
- (future) plugins/: Plugin registration and discovery
- (future) audit/: Audit logging
- (future) events/: Event bus and event handling
- (future) commands/: Command framework
- (future) i18n/: Internationalization and localization
"""

from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

__all__ = [
    "OperationResult",
    "OperationStatus",
]
