"""Infrastructure modules for the SRE Bot application.

Centralized infrastructure components:
- configuration: Settings management (settings, RetrySettings)
- auth: Authentication and identity resolution (identity_resolver, validate_jwt_token)
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
"""

# Configuration
from infrastructure.configuration import settings

# Auth & Identity
from infrastructure.auth import identity_resolver, UserIdentity, validate_jwt_token

# Observability
from infrastructure.observability import get_module_logger, logger

# Operations (legacy)
from infrastructure.operations.result import OperationResult
from infrastructure.operations.status import OperationStatus

__all__ = [
    # Configuration
    "settings",
    # Auth & Identity
    "identity_resolver",
    "UserIdentity",
    "validate_jwt_token",
    # Observability
    "get_module_logger",
    "logger",
    # Operations (legacy)
    "OperationResult",
    "OperationStatus",
]
