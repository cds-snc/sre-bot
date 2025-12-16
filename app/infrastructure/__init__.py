"""Infrastructure modules for the SRE Bot application.

Centralized infrastructure components:
- configuration: Settings management (settings, RetrySettings)
- identity: User identity models and resolution (User, IdentityResolver)
- security: JWT validation and JWKS management (validate_jwt_token, JWKSManager)
- observability: Logging and monitoring (get_module_logger, logger)
- events: Event system
- i18n: Internationalization
- idempotency: Idempotency cache
- notifications: Notification dispatcher
- operations: Operation results and error classification
- persistence: Data persistence
- resilience: Circuit breakers and retry logic
- commands: Command framework
- audit: Audit logging
- services: Dependency injection services (SettingsDep, IdentityResolverDep, get_settings)
"""

# Configuration
from infrastructure.configuration import settings

# Auth & Identity
from infrastructure.identity import User
from infrastructure.security import JWKSManager, validate_jwt_token

# Observability
from infrastructure.observability import get_module_logger, logger

# Operations (legacy)
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

# Dependency Injection Services
from infrastructure.services import (
    SettingsDep,
    IdentityResolverDep,
    get_settings,
    get_identity_resolver,
)

__all__ = [
    # Configuration
    "settings",
    # Auth & Identity
    "User",
    "JWKSManager",
    "validate_jwt_token",
    # Observability
    "get_module_logger",
    "logger",
    # Operations (legacy)
    "OperationResult",
    "OperationStatus",
    # Dependency Injection Services
    "SettingsDep",
    "IdentityResolverDep",
    "get_settings",
    "get_identity_resolver",
]
