"""Infrastructure layer - dependency injection and core services.

Public API:
- Dependency injection providers (get_settings, etc.)
- Type aliases for FastAPI routes (SettingsDep, CurrentUserDep, etc.)
- Base types used across application (OperationResult, OperationStatus)

All other infrastructure packages are internal implementation details.
Use the services layer for all infrastructure access.
"""

# Base types (ubiquitous across the application)
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

__all__ = [
    # Base types
    "OperationResult",
    "OperationStatus",
]
