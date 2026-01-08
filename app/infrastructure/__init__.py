"""Infrastructure layer - dependency injection and core services.

Public API:
- Dependency injection providers (get_settings, get_identity_service, etc.)
- Type aliases for FastAPI routes (SettingsDep, IdentityServiceDep, etc.)
- Base types used across application (OperationResult, OperationStatus)

All other infrastructure packages are internal implementation details.
Use the services layer for all infrastructure access.
"""

# Base types (ubiquitous across the application)
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

# Dependency Injection Services (THE PUBLIC API)
from infrastructure.services import (
    SettingsDep,
    IdentityServiceDep,
    JWKSManagerDep,
    AWSClientsDep,
    get_settings,
    get_identity_service,
    get_jwks_manager,
    get_aws_clients,
)

__all__ = [
    # Base types
    "OperationResult",
    "OperationStatus",
    # Dependency Injection Services
    "SettingsDep",
    "IdentityServiceDep",
    "JWKSManagerDep",
    "AWSClientsDep",
    "get_settings",
    "get_identity_service",
    "get_jwks_manager",
    "get_aws_clients",
]
